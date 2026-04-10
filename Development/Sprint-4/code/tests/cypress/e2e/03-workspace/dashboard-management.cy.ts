describe('Dashboard Management', () => {
  beforeEach(() => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/workspace/silkroute');
      cy.wait(3000);
      cy.contains('Dashboard').click();
      cy.wait(2000);
    });
  });

  it('should display the dashboard tab', () => {
    cy.get('body').should('be.visible');
    cy.url().should('include', '/workspace/silkroute');
  });

  it('should show dashboard-related content', () => {
    cy.contains('Dashboard').should('be.visible');
  });
});
