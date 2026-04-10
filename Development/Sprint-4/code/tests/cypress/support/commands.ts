/// <reference types="cypress" />

declare global {
  namespace Cypress {
    interface Chainable {
      login(username: string, password: string): Chainable<void>;
      logout(): Chainable<void>;
    }
  }
}

Cypress.Commands.add('login', (username: string, password: string) => {
  cy.session([username, password], () => {
    cy.visit('/login');
    cy.wait(1500);

    cy.get('input').eq(0).clear().type(username);
    cy.get('input[type="password"]').clear().type(password);
    cy.get('button[type="submit"]').click();

    cy.url().should('include', '/dashboard', { timeout: 15000 });

    cy.window().then((win) => {
      expect(win.localStorage.getItem('access_token')).to.exist;
    });
  }, {
    cacheAcrossSpecs: true,
  });
});

Cypress.Commands.add('logout', () => {
  cy.window().then((win) => {
    win.localStorage.removeItem('access_token');
    win.localStorage.removeItem('user');
  });
  cy.visit('/');
});

export {};
