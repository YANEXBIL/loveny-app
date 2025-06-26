/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html", // Scans HTML files in the main templates directory
    "./*/templates/**/*.html", // Scans HTML files in app-specific templates directories (like accounts/templates)
  ],
  theme: {
    extend: {
        fontFamily: {
            sans: ['Inter', 'sans-serif'], // Define 'sans' to use Inter font
        },
        colors: {
            'pink-500': '#ec4899', // Example, adjust if your pink is different
            'purple-600': '#9333ea', // Example, adjust if your purple is different
            // Add any other custom colors here
        },
    },
  },
  plugins: [],
}