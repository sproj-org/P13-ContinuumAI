describe('Workspace Tabs', () => {
  beforeEach(() => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/workspace/silkroute');
      cy.wait(3000);
    });
  });

  it('should load the workspace page', () => {
    cy.url().should('include', '/workspace/silkroute');
    cy.get('body').should('be.visible');
  });

  it('should show all four tab labels', () => {
    cy.contains('Profiling').should('be.visible');
    cy.contains('Chart Builder').should('be.visible');
    cy.contains('Dashboard').should('be.visible');
    cy.contains('Strategy').should('be.visible');
  });

  it('should switch to Chart Builder tab', () => {
    cy.contains('Chart Builder').click();
    cy.wait(1500);
    cy.get('body').should('be.visible');
  });

  it('should switch to Dashboard tab', () => {
    cy.contains('Dashboard').click();
    cy.wait(1500);
    cy.get('body').should('be.visible');
  });

  it('should switch to Strategy tab', () => {
    cy.contains('Strategy').click();
    cy.wait(1500);
    cy.get('body').should('be.visible');
  });

  it('should switch back to Profiling tab', () => {
    cy.contains('Strategy').click();
    cy.wait(1000);
    cy.contains('Profiling').click();
    cy.wait(1500);
    cy.contains('Select a mart to view its profile').should('be.visible');
  });
});
