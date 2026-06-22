"""
CT.Gov Fetcher — 从 ClinicalTrials.gov 检索研究文档和元数据。

功能:
  · 按条件/分期/状态搜索临床试验
  · 获取单个研究 (NCT ID) 的完整信息
  · 列出可下载的文档 (Protocol, SAP, ICF)
  · 下载 PDF 文档到本地

设计约束:
  · 确定性, 纯函数 (下载部分除外)
  · 遵守 5 req/s 速率限制
  · 不修改下载的文档
  · 输出标准化元数据结构
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests


# ── Data Models ───────────────────────────────────────────────────


@dataclass
class CTGovDocument:
    """ClinicalTrials.gov 上的可下载文档"""
    doc_id: str                # largeDocId, 如 "NCT04205812_001"
    filename: str              # 原始文件名, 如 "Protocol_NSCLC_v3.pdf"
    doc_type: str              # "PROTOCOL" | "SAP" | "ICF"
    upload_date: str           # 上传日期 "YYYY-MM-DD"
    size_bytes: int = 0        # 文件大小 (bytes)
    download_url: str = ""     # 下载 URL


@dataclass
class CTGovStudy:
    """临床试验基本信息"""
    nct_id: str
    brief_title: str
    official_title: str = ""
    phase: str = ""
    overall_status: str = ""
    study_type: str = ""            # INTERVENTIONAL | OBSERVATIONAL
    enrollment: int = 0
    conditions: list[str] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    sponsor: str = ""
    start_date: str = ""
    primary_completion_date: str = ""
    documents: list[CTGovDocument] = field(default_factory=list)


@dataclass
class CTGovSearchResult:
    """搜索结果"""
    total_count: int
    studies: list[CTGovStudy]
    next_page_token: str = ""


# ── API Client ────────────────────────────────────────────────────


class CTGovClient:
    """
    ClinicalTrials.gov API v2 客户端

    速率限制: 5 req/s (自动遵守, 通过 rate_limit 参数配置)
    认证: 不需要 (公开 API)
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2"
    CDN_URL = "https://cdn.clinicaltrials.gov/large-docs"

    def __init__(self, rate_limit: float = 0.25, download_dir: str = "downloads/ctgov"):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": (
                "ClinicalWorkflow/3.0 (research-use; "
                "contact@example.com)"
            ),
        })
        self.rate_limit = rate_limit
        self.download_dir = Path(download_dir)
        self._last_request = 0.0

    # ── 速率限制 ──────────────────────────────────────────────

    def _respect_rate_limit(self):
        """确保不超过 5 req/s 的速率限制"""
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    # ── 搜索研究 ──────────────────────────────────────────────

    def search_studies(
        self,
        query: Optional[str] = None,
        condition: Optional[str] = None,
        intervention: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        fields: Optional[list[str]] = None,
    ) -> CTGovSearchResult:
        """
        搜索临床试验。

        参数:
          query:        自由文本搜索词
          condition:    疾病/条件 (e.g. "Non-Small Cell Lung Cancer")
          intervention: 干预措施 (e.g. "pembrolizumab")
          phase:        试验阶段 (e.g. "Phase 3")
          status:       试验状态 (e.g. "RECRUITING", "COMPLETED")
          page_size:    每页结果数 (max 1000)
          page_token:   分页 token
          fields:       指定返回字段列表

        返回:
          CTGovSearchResult 包含匹配的研究和分页信息
        """
        params: dict[str, Any] = {
            "format": "json",
            "pageSize": min(page_size, 1000),
        }
        if query:
            params["query.term"] = query
        if condition:
            params["query.cond"] = condition
        if intervention:
            params["query.intr"] = intervention
        if phase:
            params["query.phase"] = phase
        if status:
            params["filter.overallStatus"] = status
        if page_token:
            params["pageToken"] = page_token
        if fields:
            params["fields"] = ",".join(fields)

        self._respect_rate_limit()
        resp = self.session.get(f"{self.BASE_URL}/studies", params=params)
        resp.raise_for_status()
        data = resp.json()

        studies = [self._parse_study_brief(s) for s in data.get("studies", [])]
        return CTGovSearchResult(
            total_count=data.get("totalCount", 0),
            studies=studies,
            next_page_token=data.get("nextPageToken", ""),
        )

    # ── 获取单个研究 ──────────────────────────────────────────

    def get_study(self, nct_id: str) -> CTGovStudy:
        """
        获取单个研究的完整信息, 包括可下载文档列表。

        参数:
          nct_id: NCT 编号, 如 "NCT04205812"

        返回:
          CTGovStudy 包含完整的研究信息和文档列表
        """
        self._respect_rate_limit()
        resp = self.session.get(
            f"{self.BASE_URL}/studies/{nct_id}",
            params={"format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

        return self._parse_study_full(nct_id, data)

    # ── 列出文档 ──────────────────────────────────────────────

    def list_documents(self, nct_id: str) -> list[CTGovDocument]:
        """
        列出某个研究的所有可下载文档 (Protocol, SAP, ICF)。

        参数:
          nct_id: NCT 编号

        返回:
          文档列表 (可能为空, 如果该研究未上传文档)
        """
        study = self.get_study(nct_id)
        return study.documents

    # ── 下载文档 ──────────────────────────────────────────────

    def download_document(
        self,
        document: CTGovDocument,
        output_dir: Optional[str] = None,
    ) -> Path:
        """
        下载单个文档到本地。

        参数:
          document:   CTGovDocument 对象 (从 list_documents 获取)
          output_dir: 输出目录 (默认: self.download_dir / NCT_ID)

        返回:
          本地文件路径

        引发:
          RuntimeError: 下载失败或文档不可用
        """
        url = document.download_url
        if not url:
            raise RuntimeError(
                f"No download URL available for {document.doc_id}. "
                f"The document '{document.filename}' may not be publicly accessible."
            )

        # 确定输出目录
        if output_dir:
            out_path = Path(output_dir)
        else:
            nct_id = document.doc_id.rsplit("_", 1)[0]  # "NCT04205812_001" → "NCT04205812"
            out_path = self.download_dir / nct_id
        out_path.mkdir(parents=True, exist_ok=True)

        # 下载
        self._respect_rate_limit()
        resp = self.session.get(url, stream=True)
        resp.raise_for_status()

        file_path = out_path / document.filename
        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 验证
        actual_size = file_path.stat().st_size
        if document.size_bytes > 0 and actual_size != document.size_bytes:
            file_path.unlink()
            raise RuntimeError(
                f"Download incomplete for {document.filename}: "
                f"expected {document.size_bytes} bytes, got {actual_size}"
            )

        return file_path

    def download_all_documents(
        self,
        nct_id: str,
        doc_types: Optional[list[str]] = None,
        output_dir: Optional[str] = None,
    ) -> list[Path]:
        """
        下载某个研究的所有文档 (或按类型过滤)。

        参数:
          nct_id:    NCT 编号
          doc_types: 过滤文档类型, e.g. ["PROTOCOL", "SAP"]. None = 全部
          output_dir: 输出目录

        返回:
          已下载文件的本地路径列表
        """
        documents = self.list_documents(nct_id)

        if doc_types:
            documents = [d for d in documents if d.doc_type in doc_types]

        if not documents:
            return []

        downloaded: list[Path] = []
        for doc in documents:
            try:
                path = self.download_document(doc, output_dir)
                downloaded.append(path)
            except RuntimeError as e:
                # 单个文档下载失败不阻止其他文档
                print(f"⚠ Failed to download {doc.filename}: {e}")

        return downloaded

    # ── 翻页搜索 (谨慎使用) ───────────────────────────────────

    def search_all_pages(
        self,
        condition: Optional[str] = None,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        max_pages: int = 10,
    ) -> list[CTGovStudy]:
        """
        自动翻页获取所有搜索结果。

        ⚠ 谨慎使用: 速率限制下会较慢 (每页 0.25s + 请求时间)
        """
        all_studies: list[CTGovStudy] = []
        page_token: Optional[str] = None

        for _ in range(max_pages):
            result = self.search_studies(
                condition=condition,
                status=status,
                phase=phase,
                page_token=page_token,
            )
            all_studies.extend(result.studies)
            page_token = result.next_page_token or None
            if not page_token:
                break

        return all_studies

    # ── 解析辅助函数 ─────────────────────────────────────────

    def _parse_study_brief(self, raw: dict) -> CTGovStudy:
        """解析搜索结果中的简要研究信息"""
        ps = raw.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        status_m = ps.get("statusModule", {})
        design = ps.get("designModule", {})

        return CTGovStudy(
            nct_id=ident.get("nctId", ""),
            brief_title=ident.get("briefTitle", ""),
            official_title=ident.get("officialTitle", ""),
            phase=self._format_phases(design.get("phases", [])),
            overall_status=status_m.get("overallStatus", ""),
            study_type=design.get("studyType", ""),
            enrollment=design.get("enrollmentInfo", {}).get("count", 0) or 0,
            conditions=ident.get("conditions", []),
            sponsor=ident.get("organization", {}).get("fullName", ""),
            start_date=self._format_date(status_m.get("startDateStruct")),
            primary_completion_date=self._format_date(
                status_m.get("primaryCompletionDateStruct")
            ),
        )

    def _parse_study_full(self, nct_id: str, data: dict) -> CTGovStudy:
        """解析完整的 API 响应"""
        ps = data.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        status_m = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        arms = ps.get("armsInterventionsModule", {})

        # 解析文档
        doc_section = ps.get("documentSection", {})
        large_doc_module = doc_section.get("largeDocModule", {})
        documents = self._parse_documents(nct_id, large_doc_module)

        # 解析干预措施
        interventions = [
            inv.get("interventionName", "")
            for inv in arms.get("interventions", [])
        ]

        return CTGovStudy(
            nct_id=nct_id,
            brief_title=ident.get("briefTitle", ""),
            official_title=ident.get("officialTitle", ""),
            phase=self._format_phases(design.get("phases", [])),
            overall_status=status_m.get("overallStatus", ""),
            study_type=design.get("studyType", ""),
            enrollment=design.get("enrollmentInfo", {}).get("count", 0) or 0,
            conditions=list(ident.get("conditions", [])),
            interventions=interventions,
            sponsor=ident.get("organization", {}).get("fullName", ""),
            start_date=self._format_date(status_m.get("startDateStruct")),
            primary_completion_date=self._format_date(
                status_m.get("primaryCompletionDateStruct")
            ),
            documents=documents,
        )

    def _parse_documents(
        self, nct_id: str, large_doc_module: dict
    ) -> list[CTGovDocument]:
        """解析文档列表并构造下载 URL"""
        if not large_doc_module:
            return []

        docs = large_doc_module.get("largeDocs", [])
        result: list[CTGovDocument] = []

        for doc in docs:
            doc_id = doc.get("largeDocId", "")
            filename = doc.get("filename", "")
            doc_type = doc.get("type", "")  # PROTOCOL | SAP | ICF

            # 构造下载 URL
            # 格式: https://cdn.clinicaltrials.gov/large-docs/{first_2}/{NCT}/{docId}_{filename}
            nct_number = nct_id.replace("NCT", "")
            first_two = nct_number[:2]
            download_url = (
                f"{self.CDN_URL}/{first_two}/{nct_id}/{doc_id}_{filename}"
            )

            result.append(CTGovDocument(
                doc_id=doc_id,
                filename=filename,
                doc_type=doc_type,
                upload_date=doc.get("uploadDate", ""),
                download_url=download_url,
            ))

        return result

    @staticmethod
    def _format_phases(phases: list[str]) -> str:
        return ", ".join(phases) if phases else ""

    @staticmethod
    def _format_date(date_struct: Optional[dict]) -> str:
        if not date_struct:
            return ""
        return date_struct.get("date", "") or ""


# ── MCP Tool 接口函数 ──────────────────────────────────────────────


def search_ctgov(
    condition: Optional[str] = None,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    term: Optional[str] = None,
    page_size: int = 20,
    max_pages: int = 5,
) -> dict[str, Any]:
    """
    MCP Tool: ctgov_search

    搜索 ClinicalTrials.gov 上的临床试验。
    用于分析协议时查找参考试验、了解标准终点和入排标准。

    Args:
      condition: 疾病/条件, e.g. "Non-Small Cell Lung Cancer"
      phase:     试验阶段, e.g. "Phase 3"
      status:    试验状态, e.g. "RECRUITING"
      term:      自由文本搜索
      page_size: 每页结果数
      max_pages: 最大翻页数
    """
    client = CTGovClient()

    if max_pages > 1:
        studies = client.search_all_pages(
            condition=condition,
            status=status,
            phase=phase,
            max_pages=max_pages,
        )
    else:
        result = client.search_studies(
            query=term,
            condition=condition,
            phase=phase,
            status=status,
            page_size=page_size,
        )
        studies = result.studies

    return {
        "total_found": len(studies),
        "studies": [
            {
                "nct_id": s.nct_id,
                "brief_title": s.brief_title,
                "phase": s.phase,
                "status": s.overall_status,
                "enrollment": s.enrollment,
                "conditions": s.conditions,
                "sponsor": s.sponsor,
                "start_date": s.start_date,
                "completion_date": s.primary_completion_date,
            }
            for s in studies
        ],
    }


def get_study_details(nct_id: str) -> dict[str, Any]:
    """
    MCP Tool: ctgov_study_detail

    获取单个研究的完整信息，包括所有可下载文档。

    Args:
      nct_id: NCT 编号, e.g. "NCT04205812"
    """
    client = CTGovClient()
    study = client.get_study(nct_id)

    return {
        "nct_id": study.nct_id,
        "brief_title": study.brief_title,
        "official_title": study.official_title,
        "phase": study.phase,
        "overall_status": study.overall_status,
        "study_type": study.study_type,
        "enrollment": study.enrollment,
        "conditions": study.conditions,
        "interventions": study.interventions,
        "sponsor": study.sponsor,
        "start_date": study.start_date,
        "primary_completion_date": study.primary_completion_date,
        "documents": [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "type": d.doc_type,
                "upload_date": d.upload_date,
                "available": bool(d.download_url),
            }
            for d in study.documents
        ],
        "documents_available": len(study.documents),
    }


def download_study_documents(
    nct_id: str,
    doc_types: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    MCP Tool: ctgov_download_docs

    下载某个试验的文档 (Protocol, SAP, ICF)。

    Args:
      nct_id:    NCT 编号
      doc_types: 文档类型过滤, e.g. ["PROTOCOL", "SAP"]. None = 全部
      output_dir: 输出目录 (默认: project/downloads/ctgov/{NCT_ID}/)
    """
    client = CTGovClient(download_dir=output_dir or "downloads/ctgov")
    paths = client.download_all_documents(nct_id, doc_types, output_dir)

    return {
        "nct_id": nct_id,
        "downloaded": len(paths),
        "files": [str(p) for p in paths],
    }


# ── 诊断函数 ────────────────────────────────────────────────────────


def check_document_availability(nct_ids: list[str]) -> list[dict[str, Any]]:
    """
    批量检查哪些研究有文档可下载。

    用于 Agent 在搜索后筛选有 Protocol/SAP 的研究。
    """
    client = CTGovClient()
    results: list[dict[str, Any]] = []

    for nct_id in nct_ids:
        try:
            study = client.get_study(nct_id)
            results.append({
                "nct_id": nct_id,
                "brief_title": study.brief_title[:100],
                "total_docs": len(study.documents),
                "has_protocol": any(
                    d.doc_type == "PROTOCOL" for d in study.documents
                ),
                "has_sap": any(
                    d.doc_type == "SAP" for d in study.documents
                ),
                "documents": [
                    {"type": d.doc_type, "filename": d.filename}
                    for d in study.documents
                ],
            })
        except Exception as e:
            results.append({
                "nct_id": nct_id,
                "error": str(e),
            })

    return results
