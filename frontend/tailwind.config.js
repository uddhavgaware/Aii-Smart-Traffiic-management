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
          950: '#020617',
        },
        cyan: {
          400: '#22d3ee',
          500: '#06b6d4',
        },
        emerald: {
          400: '#34d399',
        },
        amber: {
          400: '#fbbf24',
        },
        red: {
          500: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-cyan': 'glowCyan 2s ease-in-out infinite alternate',
        'glow-red': 'glowRed 1s ease-in-out infinite alternate',
        'glow-green': 'glowGreen 2s ease-in-out infinite alternate',
        'glow-amber': 'glowAmber 0.5s ease-in-out infinite alternate',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'spin-slow': 'spin 3s linear infinite',
      },
      keyframes: {
        glowCyan: {
          '0%': { boxShadow: '0 0 5px #22d3ee, 0 0 10px #22d3ee' },
          '100%': { boxShadow: '0 0 15px #22d3ee, 0 0 30px #22d3ee, 0 0 45px #06b6d4' },
        },
        glowRed: {
          '0%': { boxShadow: '0 0 5px #ef4444, 0 0 10px #ef4444' },
          '100%': { boxShadow: '0 0 20px #ef4444, 0 0 40px #ef4444, 0 0 60px #dc2626' },
        },
        glowGreen: {
          '0%': { boxShadow: '0 0 5px #34d399, 0 0 10px #34d399' },
          '100%': { boxShadow: '0 0 15px #34d399, 0 0 30px #34d399, 0 0 45px #10b981' },
        },
        glowAmber: {
          '0%': { boxShadow: '0 0 5px #fbbf24, 0 0 10px #fbbf24' },
          '100%': { boxShadow: '0 0 15px #fbbf24, 0 0 30px #fbbf24' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backgroundImage: {
        'grid-slate': 'linear-gradient(rgba(148,163,184,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.03) 1px, transparent 1px)',
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
      backgroundSize: {
        'grid': '32px 32px',
      },
      boxShadow: {
        'glow-cyan': '0 0 15px rgba(34, 211, 238, 0.4)',
        'glow-red': '0 0 15px rgba(239, 68, 68, 0.5)',
        'glow-green': '0 0 15px rgba(52, 211, 153, 0.4)',
        'glow-amber': '0 0 15px rgba(251, 191, 36, 0.4)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.4)',
        'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.05)',
      },
    },
  },
  plugins: [],
}
