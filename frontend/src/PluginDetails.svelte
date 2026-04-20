<script>
  import { Chart } from 'chart.js/auto';
  import DOMPurify from 'dompurify';

  let { plugin = $bindable(), onaction = () => {} } = $props();

  function renderGraphs() {
    document.querySelectorAll('.line-graph').forEach(el => {
      const values = JSON.parse(el.dataset.values || '[]');
      new Chart(el, {
        type: 'line',
        data: {
          labels: values.map((_, i) => `Point ${i + 1}`),
          datasets: [{ data: values, borderColor: 'rgb(75, 192, 192)', tension: 0.1 }]
        }
      });
    });

    document.querySelectorAll('.bar-chart').forEach(el => {
      const values = JSON.parse(el.dataset.values || '[]');
      new Chart(el, {
        type: 'bar',
        data: {
          labels: values.map((_, i) => `Bar ${i + 1}`),
          datasets: [{ data: values, backgroundColor: 'rgb(54, 162, 235)' }]
        }
      });
    });

    document.querySelectorAll('.scatter-plot').forEach(el => {
      const points = JSON.parse(el.dataset.points || '[]');
      new Chart(el, {
        type: 'scatter',
        data: {
          datasets: [{
            data: points.map(p => ({ x: p[0], y: p[1] })),
            backgroundColor: 'rgb(255, 99, 132)'
          }]
        }
      });
    });
  }

  async function setupPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/setup`, { method: "POST" });
    const { payload, state } = await res.json();
    plugin = { ...plugin, status: "setup", state };
    onaction();
  }

  async function runPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/run`, { method: "POST" });
    const { payload, state, html } = await res.json();
    plugin = { ...plugin, state };
    onaction();
    if (html) {
      const htmlContainer = document.querySelector('.html-container');
      if (htmlContainer) {
        htmlContainer.innerHTML = DOMPurify.sanitize(html);
        renderGraphs();
      }
    }
  }

  async function teardownPlugin() {
    const res = await fetch(`/api/plugins/${plugin.id}/teardown`, { method: "POST" });
    const { payload, state } = await res.json();
    plugin = { ...plugin, status: "teardown", state };
    onaction();
  }

  async function killPlugin() {
    await fetch(`/api/plugins/${plugin.id}/kill`, { method: "POST" });
    plugin = null;
    onaction();
  }
</script>

{#if plugin}
  <div class="plugin-actions">
    <button
      class="btn btn-primary btn-sm"
      onclick={setupPlugin}
      disabled={plugin.status !== "uninitialized" && plugin.status !== "teardown"}
    >
      Setup
    </button>
    <button
      class="btn btn-success btn-sm"
      onclick={runPlugin}
      disabled={plugin.status !== "setup"}
    >
      Run
    </button>
    <button
      class="btn btn-error btn-sm"
      onclick={teardownPlugin}
      disabled={plugin.status !== "setup"}
    >
      Teardown
    </button>
    <button class="btn btn-error btn-sm" onclick={killPlugin}>
      Kill
    </button>
  </div>

  <div class="section">
    <h3 class="section-title">State</h3>
    <pre class="state-block">{JSON.stringify(plugin.state, null, 2)}</pre>
  </div>

  <div class="html-container"></div>
{/if}

<style>
  .plugin-actions {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .section-title {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-muted);
    margin-bottom: 0.5rem;
  }

  .state-block {
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    padding: 0.75rem;
    border-radius: 6px;
    max-height: 300px;
    overflow: auto;
    font-size: 0.85rem;
    margin: 0;
  }

  .html-container {
    margin-top: 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 1rem;
    overflow-y: auto;
    max-height: 400px;
    background: var(--color-bg);
  }

  :global(.btn-sm) {
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
  }
</style>
