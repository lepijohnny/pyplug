<script>
  import { onMount } from 'svelte';
  import PluginDetails from './PluginDetails.svelte';

  let plugins = $state({});
  let selectedPlugin = $state(null);
  let theme = $state('light');

  onMount(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    fetchPlugins();
  });

  function setTheme(newTheme) {
    theme = newTheme;
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  }

  function toggleTheme() {
    setTheme(theme === 'light' ? 'dark' : 'light');
  }

  async function fetchPlugins() {
    const res = await fetch("/api/plugins");
    plugins = await res.json();
  }

  async function reloadPlugins() {
    await fetch("/reload", { method: "POST" });
    await fetchPlugins();
    selectedPlugin = null;
  }

  function selectPlugin(id) {
    selectedPlugin = plugins[id];
  }
</script>

<header class="titlebar">
  <div class="titlebar-left">
    <h1>PyPlug</h1>
    <button class="btn btn-primary btn-sm" onclick={reloadPlugins}>Reload</button>
  </div>
  <button class="theme-toggle" onclick={toggleTheme} title="Toggle theme">
    {theme === 'light' ? '\u263E' : '\u2600'}
  </button>
</header>

<div class="container">
  <div class="layout">
    <div class="plugin-list card">
      <div class="card-header">
        <h2>Plugins</h2>
      </div>
      <div class="card-body no-padding">
        {#if Object.keys(plugins).length === 0}
          <p class="empty-msg">No plugins found.</p>
        {:else}
          <ul>
            {#each Object.entries(plugins) as [id, plugin]}
              <li>
                <button
                  class="plugin-item"
                  class:selected={selectedPlugin?.id === id}
                  onclick={() => selectPlugin(id)}
                >
                  <span class="plugin-name">{plugin.name}</span>
                  <span class="status-badge status-{plugin.status}">
                    {plugin.status}
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>

    <div class="plugin-details-panel card">
      <div class="card-header">
        <h2>{selectedPlugin ? selectedPlugin.name : 'Details'}</h2>
        {#if selectedPlugin}
          <span class="status-badge status-{selectedPlugin.status}">
            {selectedPlugin.status}
          </span>
        {/if}
      </div>
      <div class="card-body">
        {#if selectedPlugin}
          <PluginDetails bind:plugin={selectedPlugin} onaction={fetchPlugins} />
        {:else}
          <p class="empty-msg">Select a plugin to view details.</p>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.5rem;
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
  }

  .titlebar-left {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .titlebar h1 {
    font-size: 1.25rem;
    font-weight: 700;
    margin: 0;
  }

  .theme-toggle {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    width: 36px;
    height: 36px;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--color-fg);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
  }

  .theme-toggle:hover {
    background: var(--color-hover);
  }

  .btn-sm {
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem;
  }

  .layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 1.5rem;
    height: calc(100vh - 120px);
  }

  .card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-surface-raised);
  }

  .card-header h2 {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0;
  }

  .card-body {
    padding: 1rem;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .card-body.no-padding {
    padding: 0;
  }

  .empty-msg {
    padding: 1rem;
    color: var(--color-muted);
  }

  .plugin-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .plugin-list li {
    border-bottom: 1px solid var(--color-border);
  }

  .plugin-list li:last-child {
    border-bottom: none;
  }

  .plugin-item {
    width: 100%;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: background 0.15s;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: none;
    border: none;
    color: inherit;
    font: inherit;
  }

  .plugin-item:hover {
    background: var(--color-hover);
  }

  .plugin-item.selected {
    background: var(--color-accent);
    color: white;
  }

  .status-badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 1rem;
    color: white;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .status-uninitialized { background: var(--color-muted); }
  .status-setup { background: var(--color-accent); }
  .status-running { background: var(--color-success); }
  .status-teardown { background: var(--color-error); }
</style>
