import path from 'path';

export default {
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.resolve(__dirname, './tests/unit/client/setup.js')],
    // Keep collection scoped to the unit modules in this repository.
    include: ['tests/unit/client/unit/**/*.{test,spec}.js'],
    deps: {
      optimizer: {
        web: {
          include: ['leaflet'],
        },
      },
    },
  },
  resolve: {
    alias: {
      // Match the source aliases used by the browser modules.
      '@app': path.resolve(__dirname, './client/packages/app/src'),
      '@core': path.resolve(__dirname, './client/packages/core/src'),
      '@test-utils': path.resolve(__dirname, './tests/unit/client/unit'),
    },
  },
};
