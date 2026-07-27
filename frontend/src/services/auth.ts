/**
 * Authentication service - AWS Amplify Cognito integration.
 *
 * Exports:
 * - configureAuth() - initialize Amplify with Cognito config
 * - login(username, password)
 * - logout()
 * - getToken() - get current JWT
 * - getUserRole() - extract role from token claims
 * - isAuthenticated() - check if session is valid
 */
