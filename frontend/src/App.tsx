import { BrowserRouter } from 'react-router';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { theme } from './theme';
import { AppRouter } from './router';

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </ThemeProvider>
  );
}
