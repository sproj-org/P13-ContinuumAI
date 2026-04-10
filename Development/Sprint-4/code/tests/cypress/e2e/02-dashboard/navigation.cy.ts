describe('Dashboard Navigation', () => {
  beforeEach(() => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
    });
  });

  it('should display dashboard page after login', () => {
    cy.visit('/dashboard');
    cy.url().should('include', '/dashboard');
    cy.get('body').should('be.visible');
  });

  it('should load available datasets from backend', () => {
    cy.intercept('GET', '**/datasets/available').as('getDatasets');
    cy.visit('/dashboard');
    cy.wait('@getDatasets', { timeout: 10000 });
    cy.get('body').should('be.visible');
  });

  it('should show user info on dashboard', () => {
    cy.visit('/dashboard');
    cy.wait(2000);
    cy.contains(/jackson/i).should('be.visible');
  });
});
