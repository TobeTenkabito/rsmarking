import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.resolve(__dirname, './tests/unit/client/setup.js')],
    // 确保匹配规则涵盖你的物理目录
    include: ['tests/unit/client/unit/**/*.{test,spec}.js'],
    deps: {
      optimizer: {
        web: {
          include: ['leaflet']
        }
      }
    },
  },
  resolve: {
    alias: {
      // 确保别名映射到 src 目录，后续导入不应再包含 src
      '@app': path.resolve(__dirname, './client/packages/app/src'),
      '@core': path.resolve(__dirname, './client/packages/core/src'),
    },
  },
});