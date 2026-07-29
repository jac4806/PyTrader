const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pytrader', {
  analyze: (tickers, options) => ipcRenderer.invoke('analyze', tickers, options),
  sendEmail: (payload) => ipcRenderer.invoke('send-email', payload),
  getConfig: (key) => ipcRenderer.invoke('get-config', key),
  setConfig: (key, value) => ipcRenderer.invoke('set-config', key, value),
});
