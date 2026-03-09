/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ghost: {
          900: '#04070f',
          700: '#10203f',
          500: '#367cff',
          300: '#74f7ff'
        }
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: 0, transform: 'translateY(20px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 12px rgba(116,247,255,.4)' },
          '50%': { boxShadow: '0 0 24px rgba(54,124,255,.7)' }
        }
      },
      animation: {
        'fade-up': 'fadeUp .8s ease-out forwards',
        'pulse-glow': 'pulseGlow 2.2s ease-in-out infinite'
      }
    }
  },
  plugins: []
};
