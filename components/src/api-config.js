class ApiConfig {
  constructor() {
    this.baseUrl = '';
    this.headers = {
        'Content-Type': 'application/json',
    };
    this.listeners = new Set();
  }
  
  setApi(baseUrl, token) {
    this.baseUrl = baseUrl

    if (!!token) {
        this.headers = {
            ...this.headers,
            'Authorization': token
        }
    }
    this.listeners.forEach(fn => fn());
  }
  
  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }
  
  getApi() {
    return {
      baseUrl: this.baseUrl,
      headers: this.headers,
    };
  }
}

export const apiConfig = new ApiConfig();
