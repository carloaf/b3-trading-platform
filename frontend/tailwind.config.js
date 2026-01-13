/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'b3-green': '#00A651',
        'b3-blue': '#003366',
        'b3-yellow': '#FFD700',
      }
    },
  },
  plugins: [],
}
