/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        gov: {
          green: "#007A33",
          "green-dark": "#005C26",
          "green-light": "#E8F5ED",
          gold: "#FFC72C",
          "gold-dark": "#E6A800",
        },
      },
    },
  },
  plugins: [],
};
