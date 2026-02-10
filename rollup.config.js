import resolve from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';
import { readFileSync } from 'fs';

const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'));
const banner = `/* Carette Widget v${pkg.version} - Widget de covoiturage embeddable */`;

export default [
  // Build principal — widget seul (ES module)
  {
    input: 'frontend/carpool-widget.js',
    output: {
      file: 'dist/carpool-widget.min.js',
      format: 'es',
      banner,
      sourcemap: true
    },
    plugins: [
      resolve(),
      terser({
        format: { comments: false },
        compress: { passes: 2, drop_console: false }
      })
    ]
  },
  // Build IIFE — pour inclusion via <script> classique (non-module)
  {
    input: 'frontend/carpool-widget.js',
    output: {
      file: 'dist/carpool-widget.iife.min.js',
      format: 'iife',
      name: 'CaretteWidget',
      banner,
      sourcemap: true
    },
    plugins: [
      resolve(),
      terser({
        format: { comments: false },
        compress: { passes: 2, drop_console: false }
      })
    ]
  },
  // Payment simulator
  {
    input: 'frontend/payment-simulator.js',
    output: {
      file: 'dist/payment-simulator.min.js',
      format: 'iife',
      name: 'CarettePaymentSimulator',
      banner: `/* Carette Payment Simulator v${pkg.version} */`,
      sourcemap: true
    },
    plugins: [
      resolve(),
      terser({ format: { comments: false } })
    ]
  }
];
