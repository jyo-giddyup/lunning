// Reverse proxy: yonehiro.com/NIL* -> https://nil-predictor.fly.dev/*
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const upstreamPath = url.pathname.replace(/^\/NIL/, "") || "/";
    const upstream = new URL(upstreamPath + url.search, "https://nil-predictor.fly.dev");

    const upstreamRequest = new Request(upstream, request);
    return fetch(upstreamRequest);
  },
};
