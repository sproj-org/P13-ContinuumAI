describe('Chart Builder', () => {
  beforeEach(() => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/workspace/silkroute');
      cy.wait(3000);
      cy.contains('Chart Builder').click();
      cy.wait(2000);
    });
  });

  it('should display the chart builder panel', () => {
    cy.get('body').should('be.visible');
    cy.url().should('include', '/workspace/silkroute');
  });

  it('should show Dimensions column panel', () => {
    cy.contains('Dimensions').should('be.visible');
  });

  it('should show Measures column panel', () => {
    cy.contains('Measures').should('be.visible');
  });

  it('should show Temporal column panel', () => {
    cy.contains('Temporal').should('be.visible');
  });
});
