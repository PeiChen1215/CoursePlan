/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Microsoft YaHei", "PingFang SC", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
