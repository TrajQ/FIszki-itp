// Punkt wejścia workera pdf.js: najpierw polyfill, potem oryginalny worker
// (wektorowany bez zmian w pdfjs/). Importy modułów wykonują się w kolejności.
import "./polyfill_map.mjs";
import "./pdfjs/pdf.worker.min.mjs";
