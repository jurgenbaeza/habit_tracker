# Habit Tracker API Documentation
This document provides detailed information about the Habit Tracker API.

## Base URL
The base URL for all API endpoints is `/api/`.

## Authentication
Most endpoints require authentication using JSON Web Tokens (JWT). To authenticate, you need to obtain an access token by sending a `POST` request to the `/api/users/login/` endpoint with your username and password.

Once you have an access token, you must include it in the `Authorization` header of your requests for protected endpoints. The header should be in the format `Bearer <access_token>`.

---

# Users API
The Users API provides endpoints for user registration, login, and token management.

## `POST /api/users/register/`
Registers a new user.

### Request Body

| Parameter    | Type   | Description        |
|--------------|--------|--------------------|
| `username`   | string | **Required.** The desired username. |
| `password`   | string | **Required.** The desired password. |
| `email`      | string | The user's email address. |
| `first_name` | string | The user's first name. |
| `last_name`  | string | The user's last name. |


### Example Request
```json
{
    "username": "newuser",
    "password": "password123",
    "email": "newuser@example.com",
    "first_name": "New",
    "last_name": "User"
}
```

### Example Response (201 Created)
```json
{
    "username": "newuser",
    "email": "newuser@example.com",
    "first_name": "New",
    "last_name": "User"
}
```

## `POST /api/users/login/`
Authenticates a user and returns an access and refresh token pair.

### Request Body

| Parameter  | Type   | Description        |
|------------|--------|--------------------|
| `username` | string | **Required.** The user's username. |
| `password` | string | **Required.** The user's password. |


### Example Request
```json
{
    "username": "newuser",
    "password": "password123"
}
```

### Example Response (200 OK)
```json
{
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## `POST /api/users/login/refresh/`
Refreshes an access token using a refresh token.

### Request Body

| Parameter | Type   | Description        |
|-----------|--------|--------------------|
| `refresh` | string | **Required.** The refresh token. |


### Example Request
```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Example Response (200 OK)
```json
{
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## `GET /api/users/protected/`
A protected endpoint for testing authentication.

### Request Headers

| Header        | Value               |
|---------------|---------------------|
| `Authorization` | `Bearer <access_token>` |


### Example Response (200 OK)
```json
{
    "message": "This is a protected endpoint for authenticated users only."
}
```

---

# Habits API
The Habits API provides endpoints for managing habits and habit logs.

## `POST /api/habits/log/`
Creates a new log for a specific habit.

### Request Headers

| Header        | Value               |
|---------------|---------------------|
| `Authorization` | `Bearer <access_token>` |


### Request Body

| Parameter | Type    | Description                               |
|-----------|---------|-------------------------------------------|
| `habit`   | integer | **Required.** The ID of the habit to log. |


### Example Request
```json
{
    "habit": 1
}
```

### Example Response (201 Created)
```json
{
    "habit": 1
}
```
