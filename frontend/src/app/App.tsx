import { RouterProvider } from 'react-router';
import { router } from './routes';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { AuthGate } from './components/AuthGate';

export default function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AuthGate>
          <RouterProvider router={router} />
        </AuthGate>
      </LanguageProvider>
    </ThemeProvider>
  );
}
