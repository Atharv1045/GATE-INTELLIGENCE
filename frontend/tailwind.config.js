/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060B19',
          900: '#0B132B',
          800: '#1C2541',
          700: '#2A365F',
        },
      },
    },
  },
  plugins: [],
};
