describe('Authentication', () => {

  it('should redirect to login when not authenticated', () => {
    cy.visit('/dashboard');
    cy.url().should('include', '/login', { timeout: 10000 });
  });

  it('should display login page elements', () => {
    cy.visit('/login');
    cy.wait(1500);
    cy.get('input').should('have.length.at.least', 2);
    cy.get('button[type="submit"]').should('exist');
  });

  it('should login successfully with valid credentials', () => {
    cy.fixture('user').then((user) => {
      cy.visit('/login');
      cy.wait(1500);
      cy.get('input').eq(0).type(user.username);
      cy.get('input[type="password"]').type(user.password);
      cy.get('button[type="submit"]').click();
      cy.url().should('include', '/dashboard', { timeout: 15000 });
      cy.window().then((win) => {
        expect(win.localStorage.getItem('access_token')).to.exist;
      });
    });
  });

  it('should stay on login page with invalid credentials', () => {
    cy.visit('/login');
    cy.wait(1500);
    cy.get('input').eq(0).type('wronguser');
    cy.get('input[type="password"]').type('wrongpass');
    cy.get('button[type="submit"]').click();
    cy.wait(3000);
    cy.url().should('include', '/login');
  });

  it('should maintain session after page reload', () => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/dashboard');
      cy.reload();
      cy.url().should('include', '/dashboard', { timeout: 10000 });
    });
  });

  it('should redirect to login after clearing token', () => {
    cy.fixture('user').then((user) => {
      cy.login(user.username, user.password);
      cy.visit('/dashboard');
      cy.wait(2000);
      cy.window().then((win) => {
        win.localStorage.removeItem('access_token');
        win.localStorage.removeItem('user');
      });
      cy.visit('/dashboard');
      cy.url().should('include', '/login', { timeout: 10000 });
    });
  });
});
