# Plugin HTML Components

Plugins can return HTML to render in the PyPlug shell. Use the following components for consistency:

## Buttons
```html
<button class="btn btn-primary">Primary</button>
<button class="btn btn-success">Success</button>
<button class="btn btn-error">Error</button>
```

## Cards
```html
<div class="card">
  <h3>Card Title</h3>
  <p class="text">Card content</p>
</div>
```

## Graphs

### Line Graph
```html
<div class="graph-container">
  <h3 class="text">Line Graph</h3>
  <canvas class="line-graph" data-values="[1, 2, 3, 4, 5]"></canvas>
</div>
```

### Bar Chart
```html
<div class="graph-container">
  <h3 class="text">Bar Chart</h3>
  <canvas class="bar-chart" data-values="[10, 20, 30, 40]"></canvas>
</div>
```

### Scatter Plot
```html
<div class="graph-container">
  <h3 class="text">Scatter Plot</h3>
  <canvas class="scatter-plot" data-points="[[1,2], [3,4], [5,6]]"></canvas>
</div>
```

### Image Graph
```html
<div class="graph-container">
  <h3 class="text">Image Graph</h3>
  <img class="image-graph" src="data:image/png;base64,..." alt="Graph" />
</div>
```

## Rules
1. **No Inline Styles**: Use shell classes only.
2. **No Scripts**: Scripts are stripped for security.
3. **Sanitized**: HTML is sanitized before rendering.
