import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      'react-hooks/set-state-in-effect': 'off',
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['src/features/**/*.{ts,tsx}', 'src/app/**/*.{ts,tsx}', 'src/App.tsx'],
    ignores: [
      'src/features/**/__tests__/**',
      'src/features/**/*.test.{ts,tsx}',
      'src/features/**/*.spec.{ts,tsx}',
      'src/features/**/hooks/**',
      'src/features/**/model/**',
      'src/features/**/services/**',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          {
            name: '@/lib/attractorClient',
            message: 'Presentation files must not call API clients directly. Move API usage into feature hooks, services, or model loaders.',
          },
          {
            name: '@/lib/workspaceClient',
            message: 'Presentation files must not call API clients directly. Move API usage into feature hooks, services, or model loaders.',
          },
          {
            name: '@/lib/apiClient',
            message: 'Presentation files must not call API clients directly. Move API usage into feature hooks, services, or model loaders.',
          },
          {
            name: '@/lib/validatedApiClient',
            message: 'Presentation files must not call API clients directly. Move API usage into feature hooks, services, or model loaders.',
          },
        ],
        patterns: [
          {
            group: ['@/lib/api/*'],
            message: 'Presentation files must not import API client modules directly.',
          },
          {
            group: ['@/components/*'],
            message: 'The generic @/components layer was removed. Use @/ui/* for shared primitives or @/features/* for feature code.',
          },
        ],
      }],
    },
  },
  {
    files: ['src/features/**/*.{tsx}', 'src/app/**/*.{tsx}', 'src/App.tsx'],
    ignores: [
      'src/features/**/__tests__/**',
      'src/features/**/*.test.{tsx}',
      'src/features/**/*.spec.{tsx}',
      'src/features/**/hooks/**',
      'src/features/**/model/**',
      'src/features/**/services/**',
      'src/features/workflow-canvas/**',
    ],
    rules: {
      'no-restricted-syntax': ['error',
        {
          selector: "JSXOpeningElement[name.name='button']",
          message: 'Use @/ui Button for non-canvas feature controls.',
        },
        {
          selector: "JSXOpeningElement[name.name='input']",
          message: 'Use @/ui Input for non-canvas feature controls.',
        },
        {
          selector: "JSXOpeningElement[name.name='select']",
          message: 'Use @/ui NativeSelect or Select for non-canvas feature controls.',
        },
        {
          selector: "JSXOpeningElement[name.name='textarea']",
          message: 'Use @/ui Textarea for non-canvas feature controls.',
        },
        {
          selector: "JSXOpeningElement[name.name='label']",
          message: 'Use @/ui Label or FieldRow for non-canvas feature forms.',
        },
      ],
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: [
      'src/**/__tests__/**',
      'src/**/*.test.{ts,tsx}',
      'src/**/*.spec.{ts,tsx}',
      'src/ui/dialog-controller.tsx',
    ],
    rules: {
      'no-restricted-globals': ['error',
        {
          name: 'alert',
          message: 'Use useDialogController from @/ui for non-canvas alerts.',
        },
        {
          name: 'confirm',
          message: 'Use useDialogController from @/ui for non-canvas confirmations.',
        },
        {
          name: 'prompt',
          message: 'Use useDialogController from @/ui for non-canvas prompts.',
        },
      ],
      'no-restricted-properties': ['error',
        {
          object: 'window',
          property: 'alert',
          message: 'Use useDialogController from @/ui for non-canvas alerts.',
        },
        {
          object: 'window',
          property: 'confirm',
          message: 'Use useDialogController from @/ui for non-canvas confirmations.',
        },
        {
          object: 'window',
          property: 'prompt',
          message: 'Use useDialogController from @/ui for non-canvas prompts.',
        },
      ],
    },
  },
])
