// Configuración de ESLint para el frontend (React + TypeScript).
//
// Usa el formato plano (flat config) de ESLint 9 en adelante. Se parte de las
// reglas recomendadas de ESLint y typescript-eslint, y se suman las dos que
// importan en una app de React con Vite: el uso correcto de los hooks y el
// contrato del recargado en caliente.

import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // Lo generado por la compilación no es código nuestro.
  { ignores: ['dist', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Avisa cuando un archivo exporta algo además del componente: rompe el
      // recargado en caliente de Vite. Es aviso, no error.
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // Las pantallas cargan sus datos con un useEffect que llama al API y
      // guarda el resultado en el estado. La regla desaconseja ese patrón por
      // los renders en cascada que provoca; aquí se deja como aviso porque es
      // la forma en que está escrita toda la aplicación y cambiarla es un
      // rediseño de la capa de datos, no un ajuste de estilo. Queda visible
      // para atenderlo cuando se migre a un cliente de datos con caché.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
)
