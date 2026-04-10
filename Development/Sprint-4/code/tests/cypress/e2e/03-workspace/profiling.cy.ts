describe('Profiling Tab', () => {
  beforeEach(() => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/workspace/silkroute');
      cy.wait(3000);
      cy.contains('Profiling').click();
      cy.wait(1500);
    });
  });

  it('should display the profiling panel prompt', () => {
    cy.contains('Select a mart to view its profile').should('be.visible');
  });

  it('should show Sales Daily mart', () => {
    cy.contains('Sales Daily').should('be.visible');
  });

  it('should show Store-SKU Daily mart', () => {
    cy.contains('Store-SKU Daily').should('be.visible');
  });

  it('should show Store 360 mart', () => {
    cy.contains('Store 360').should('be.visible');
  });

  it('should show Product 360 mart', () => {
    cy.contains('Product 360').should('be.visible');
  });

  it('should show Customer 360 mart', () => {
    cy.contains('Customer 360').should('be.visible');
  });

  it('should show Employee 360 mart', () => {
    cy.contains('Employee 360').should('be.visible');
  });

  it('should show Inventory Health Daily mart', () => {
    cy.contains('Inventory Health Daily').should('be.visible');
  });
});
