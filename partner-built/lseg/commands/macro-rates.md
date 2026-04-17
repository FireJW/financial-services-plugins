# API Reference

## Client-Side JavaScript API

The Turnstile JavaScript API is available at `window.turnstile` after loading the script.

### `turnstile.render(container, options)`

Renders a Turnstile widget into a container element.

**Parameters:**
- `container` (string | HTMLElement): CSS selector or DOM element
- `options` (TurnstileOptions): Configuration object (see [configuration.md](configuration.md))

**Returns:** `string` - Widget ID for use with other API methods

**Example:**
```javascript
const widgetId = window.turnstile.render('#my-container', {
  sitekey: 'YOUR_SITE_KEY',
  callback: (token) => console.log('Success:', token),
  'error-callback': (code) => console.error('Error:', code)
});
```

### `turnstile.reset(widgetId)`

Resets a widget (clears token, resets challenge state). Useful when form validation fails.

**Parameters:**
- `widgetId` (string): Widget ID from `render()`, or container element

**Returns:** `void`

**Example:**
```javascript
// Reset on form error
if (!validateForm()) {
  window.turnstile.reset(widgetId);
}
```

### `turnstile.remove(widgetId)`

Removes a widget from the DOM completely.

**Parameters:**
- `widgetId` (string): Widget ID from `render()`

**Returns:** `void`

**Example:**
```javascript
// Cleanup on navigation
window.turnstile.remove(widgetId);
```

### `turnstile.getResponse(widgetId)`

Gets the current token from a widget (if challenge completed).

**Parameters:**
- `widgetId` (string): Widget ID from `render()`, or container element

**Returns:** `string | undefined` - Token string, or undefined if not ready

**Example:**
```javascript
const token = window.turnstile.getResponse(widgetId);
if (token) {
  submitForm(token);
}
```

### `turnstile.isExpired(widgetId)`

Checks if a widget's token has expired (>5 minutes old).

**Parameters:**
- `widgetId` (string): Widget ID from `render()`

**Returns:** `boolean` - True if expired

**Example:**
```javascript
if (window.turnstile.isExpired(widgetId)) {
  window.turnstile.reset(widgetId);
}
```

## Callback Signatures

```typescript
type TurnstileCallback = (token: string) => void;
type ErrorCallback = (errorCode: string) => void;
type TimeoutCallback = () => void;
type ExpiredCallback = () => void;
type BeforeInteractiveCallback = () => void;
type AfterInteractiveCallback = () => void;
type UnsupportedCallback = () => vo