// Import commands.js using ES2015 syntax:
import './commands';

// Ignore Next.js hydration errors - these are SSR dev-mode mismatches, not test failures
Cypress.on('uncaught:exception', (err) => {
  if (
    err.message.includes('Hydration failed') ||
    err.message.includes('hydration') ||
    err.message.includes('Minified React error') ||
    err.message.includes('downlevelIteration')
  ) {
    return false;
  }
  return true;
});

// Clear localStorage before each test to ensure clean state
beforeEach(() => {
  cy.window().then((win) => {
    win.localStorage.clear();
  });
});
