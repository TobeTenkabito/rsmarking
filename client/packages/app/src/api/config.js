const fallbackOrigin = window.location.origin;
const config = window.RSMARKING_CONFIG || {};

function trimTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

export const API_CONFIG = {
  dataServiceUrl: trimTrailingSlash(config.dataServiceUrl || fallbackOrigin),
  annotationServiceUrl: trimTrailingSlash(config.annotationServiceUrl || 'http://localhost:8001'),
  vectorTileServiceUrl: trimTrailingSlash(config.vectorTileServiceUrl || 'http://localhost:8003'),
  executorServiceUrl: trimTrailingSlash(config.executorServiceUrl || 'http://localhost:8004'),
  tileServiceUrl: trimTrailingSlash(config.tileServiceUrl || 'http://localhost:8005'),
  aiGatewayUrl: trimTrailingSlash(config.aiGatewayUrl || 'http://localhost:8006'),
};
