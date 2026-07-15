export class ReviewClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
  }

  async health() {
    return this.#request("/api/v1/health");
  }

  async listReviews() {
    return this.#request("/api/v1/reviews");
  }

  async getReview(queueId, reviewId) {
    return this.#request(`/api/v1/reviews/${encodeURIComponent(queueId)}/${encodeURIComponent(reviewId)}`);
  }

  async getSource(queueId, reviewId, sourceIndex) {
    return this.#request(
      `/api/v1/reviews/${encodeURIComponent(queueId)}/${encodeURIComponent(reviewId)}/sources/${sourceIndex}`,
    );
  }

  async submitDecision(queueId, reviewId, payload) {
    return this.#request(`/api/v1/reviews/${encodeURIComponent(queueId)}/${encodeURIComponent(reviewId)}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async #request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      credentials: "same-origin",
      ...options,
    });
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error?.message || payload?.detail || `Request failed: ${response.status}`;
      const error = new Error(message);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }
}

