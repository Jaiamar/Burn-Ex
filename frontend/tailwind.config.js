/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          50: '#F8FAFC',
          500: '#64748B',
          900: '#0F172A',
        },
        blue: {
          600: '#2563EB',
        },
        emerald: {
          500: '#10B981',
        },
        red: {
          500: '#EF4444',
        }
      }
    },
  },
  plugins: [],
}
