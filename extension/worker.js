let socket;
let connecting = false;
let enabled = true;
const owners = new Map();
const groups = new Map();
const approvals = new Map();
const scripts = new Map();
const queues = new Map();
const downloads = new Map();
const IDLE_MS = 5 * 60 * 1000;
const pendingDownloads = [];
let lastError = "Not connected";

function send(message) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

async function release(owner) {
  for (const [tabId, record] of owners) {
    if (owner && record.owner !== owner) continue;
    try {
      for (const event of record.heldKeys?.values() || []) {
        await chrome.debugger.sendCommand({tabId}, "Input.dispatchKeyEvent", {...event, type:"keyUp", text:undefined});
      }
      if (record.heldMouse) await chrome.debugger.sendCommand({tabId}, "Input.dispatchMouseEvent", {...record.heldMouse, type:"mouseReleased", buttons:0});
      await chrome.debugger.sendCommand({tabId}, "Page.stopScreencast");
      await chrome.debugger.sendCommand({tabId}, "Emulation.setFocusEmulationEnabled", {enabled:false});
      const script = scripts.get(tabId);
      if (script) await chrome.debugger.sendCommand({tabId}, "Page.removeScriptToEvaluateOnNewDocument", {identifier: script});
      await chrome.debugger.sendCommand({tabId}, "Runtime.evaluate", {
        expression: "document.getElementById('__spirit_overlay__')?.remove()"
      });
    } catch {}
    try { await chrome.debugger.detach({tabId}); } catch {}
    try {
      if (record.groupId >= 0) await chrome.tabs.group({tabIds: [tabId], groupId: record.groupId});
      else await chrome.tabs.ungroup(tabId);
    } catch {}
    owners.delete(tabId);
    scripts.delete(tabId);
  }
  for (const [id, approval] of approvals) {
    if (!owner || approval.owner === owner) {
      approval.resolve(false);
      approvals.delete(id);
      chrome.windows.remove(approval.windowId).catch(() => {});
    }
  }
}

async function claim(tabId, owner) {
  const current = owners.get(tabId);
  if (current) {
    if (current.owner !== owner) throw new Error("This tab is controlled by another SPIRIT session");
    current.lastUsed = Date.now();
    return;
  }
  const tab = await chrome.tabs.get(tabId);
  if (!/^(https?:|file:|about:blank$)/.test(tab.url || "")) {
    throw new Error("Chrome internal pages and extension pages require manual interaction");
  }
  await chrome.debugger.attach({tabId}, "1.3");
  owners.set(tabId, {owner, groupId: tab.groupId, lastUsed: Date.now(), heldKeys:new Map()});
  try {
    let groupId = groups.get(tab.windowId);
    if (groupId !== undefined) {
      try { await chrome.tabGroups.get(groupId); } catch { groupId = undefined; }
    }
    groupId = await chrome.tabs.group({tabIds: [tabId], ...(groupId === undefined ? {} : {groupId})});
    await chrome.tabGroups.update(groupId, {title: "SPIRIT", color: "purple", collapsed: false});
    groups.set(tab.windowId, groupId);
  } catch (error) {
    await chrome.debugger.detach({tabId}).catch(() => {});
    owners.delete(tabId);
    throw error;
  }
}

async function confirm(request) {
  const id = crypto.randomUUID();
  const pending = new Promise(resolve => {
    approvals.set(id, {resolve, owner: request.owner, message: request.message, windowId: null});
  });
  const window = await chrome.windows.create({
    url: chrome.runtime.getURL(`approval.html?id=${id}`), type: "popup", width: 490, height: 390,
    focused: true
  });
  const record = approvals.get(id);
  if (record) record.windowId = window.id;
  const timer = setTimeout(() => {
    approvals.get(id)?.resolve(false);
    approvals.delete(id);
    chrome.windows.remove(window.id).catch(() => {});
  }, 110000);
  try { return {approved: await pending}; }
  finally { clearTimeout(timer); approvals.delete(id); }
}

async function dispatch(request) {
  const {action, owner} = request;
  const tabId = Number(request.tab);
  if (action === "status") return {connected: true, version: chrome.runtime.getManifest().version};
  if (action === "tabs") {
    return (await chrome.tabs.query({})).filter(t => !t.incognito).map(t => ({
      id: String(t.id), title: t.title || "", url: t.url || "", active: t.active,
      window_id: t.windowId, group_id: t.groupId, controlled: owners.has(t.id),
      favicon: t.favIconUrl || "", domain: (() => {try {return new URL(t.url).hostname;} catch {return "";}})()
    }));
  }
  if (action === "release") { await release(owner); return {}; }
  if (action === "confirm") return await confirm(request);
  if (action === "open") {
    if (!/^https?:\/\//.test(request.url) && request.url !== "about:blank") throw new Error("Use an HTTP(S) URL");
    const tab = await chrome.tabs.create({url: request.url, active: false});
    await claim(tab.id, owner);
    return {id: String(tab.id)};
  }
  await claim(tabId, owner);
  if (action === "claim") return {};
  if (action === "select") { await chrome.tabs.update(tabId, {active: true}); return {}; }
  if (action === "close") { await chrome.tabs.remove(tabId); return {}; }
  if (action === "download_setup") {
    owners.get(tabId).downloads = true;
    return {method: "chrome.downloads", destination: "Downloads/SPIRIT"};
  }
  if (action === "cdp") {
    if (!/^(Accessibility|DOM|DOMSnapshot|Input|Page|Runtime|Network|Log|Target|IO|Browser|Emulation)\./.test(request.method)) {
      throw new Error("Unsupported protocol domain");
    }
    const target = {tabId, ...(request.session ? {sessionId: request.session} : {})};
    const record = owners.get(tabId);
    if (request.method === "Input.dispatchKeyEvent") {
      if (request.params.type === "keyDown") record.heldKeys.set(request.params.key, request.params);
      if (request.params.type === "keyUp") record.heldKeys.delete(request.params.key);
    }
    if (request.method === "Input.dispatchMouseEvent") {
      if (request.params.type === "mousePressed") record.heldMouse = request.params;
      if (request.params.type === "mouseReleased") record.heldMouse = null;
    }
    const result = await chrome.debugger.sendCommand(target, request.method, request.params || {});
    if (request.method === "Page.addScriptToEvaluateOnNewDocument" && !request.session) {
      scripts.set(tabId, result.identifier);
    }
    return result || {};
  }
  if (action === "downloads") {
    const result = [];
    for (const [id, record] of downloads) {
      if (record.owner !== owner || record.tab !== tabId) continue;
      const [item] = await chrome.downloads.search({id});
      if (item) result.push({id, url: item.url, path: item.filename, name: record.name, state: item.state, error: item.error});
    }
    return result;
  }
  throw new Error("Unknown bridge action");
}

async function connect() {
  if (!enabled || connecting || socket?.readyState === WebSocket.OPEN) return;
  connecting = true;
  try {
    const config = await (await fetch(chrome.runtime.getURL("connection.json"))).json();
    const endpoint = new URL(config.url);
    if (endpoint.protocol !== "ws:" || endpoint.hostname !== "127.0.0.1" || endpoint.username || endpoint.password) throw new Error("Invalid local bridge address");
    socket = new WebSocket(config.url);
    socket.onopen = () => send({role: "extension", token: config.token});
    socket.onmessage = async event => {
      const request = JSON.parse(event.data);
      if (request.ready) {
        lastError = "";
        chrome.action.setBadgeText({text: "ON"});
        chrome.action.setBadgeBackgroundColor({color: "#7654cc"});
        return;
      }
      if (request.pong) return;
      const key = request.tab || request.owner;
      const previous = queues.get(key) || Promise.resolve();
      const job = previous.catch(() => {}).then(async () => {
        try { send({id: request.id, result: await dispatch(request)}); }
        catch (error) { send({id: request.id, error: error.message}); }
      });
      queues.set(key, job);
      job.finally(() => {if (queues.get(key) === job) queues.delete(key);});
    };
    socket.onclose = () => {
      connecting = false;
      lastError = "Local bridge disconnected";
      chrome.action.setBadgeText({text: ""});
      release();
    };
    socket.onerror = () => { lastError = "Start SPIRIT in your MCP client"; };
  } catch (error) {
    connecting = false;
    lastError = error.message;
  }
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (method === "Page.screencastFrame") {
    chrome.debugger.sendCommand(source, "Page.screencastFrameAck", {sessionId: params.sessionId}).catch(() => {});
    return;
  }
  const record = owners.get(source.tabId);
  if (method === "Page.downloadWillBegin" && record?.downloads) {
    pendingDownloads.push({owner:record.owner,tab:source.tabId,url:params.url,name:params.suggestedFilename,time:Date.now()});
    while(pendingDownloads.length>100)pendingDownloads.shift();
  }
  if (record) send({event: "cdp", owner: record.owner, tab: String(source.tabId),
    session: source.sessionId, method, params});
});
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  (async () => {
    let candidates=[];
    for(let attempt=0;attempt<10;attempt++) {
      candidates=pendingDownloads.filter(d=>Date.now()-d.time<5000 && [item.url,item.finalUrl].includes(d.url));
      if(candidates.length)break;
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    if (candidates.length !== 1) {suggest();return;}
    const record = candidates[0];pendingDownloads.splice(pendingDownloads.indexOf(record),1);
    const name = record.name.split(/[\\/]/).pop().replace(/[<>:"|?*]/g, '_');
    downloads.set(item.id, {owner: record.owner, tab: record.tab, name});
    suggest({filename: `SPIRIT/${record.owner}/${item.id}-${name}`, conflictAction: "uniquify"});
  })().catch(() => suggest());
  return true;
});
chrome.debugger.onDetach.addListener((source, reason) => {
  const record = owners.get(source.tabId);
  if (record) send({event: "detached", owner: record.owner, tab: String(source.tabId), reason});
  owners.delete(source.tabId);
});
for (const event of [chrome.tabs.onCreated, chrome.tabs.onRemoved, chrome.tabs.onUpdated, chrome.tabs.onActivated]) {
  event.addListener(() => send({event: "tabs_changed"}));
}
chrome.windows.onRemoved.addListener(windowId => {
  for (const [id, record] of approvals) {
    if (record.windowId === windowId) { record.resolve(false); approvals.delete(id); }
  }
});
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || sender.tab?.url && !sender.tab.url.startsWith(chrome.runtime.getURL(""))) return;
  if (message.action === "status") {
    respond({connected: socket?.readyState === WebSocket.OPEN && !lastError, error: lastError, tabs: owners.size});
  } else if (message.action === "tabs") {
    chrome.tabs.query({}).then(tabs=>respond(tabs.filter(t=>!t.incognito).map(t=>({id:t.id,title:t.title,url:t.url,controlled:owners.has(t.id)}))));
    return true;
  } else if (message.action === "connect") {
    enabled = true;
    connect().then(() => respond({ok: true}));
    return true;
  } else if (message.action === "stop") {
    send({event: "emergency_stop"});
    release().then(() => respond({ok: true}));
    return true;
  } else if (message.action === "approval") {
    respond({message: approvals.get(message.id)?.message || "Request expired"});
  } else if (message.action === "decide") {
    const record = approvals.get(message.id);
    if (record) {
      record.resolve(message.allow === true);
      approvals.delete(message.id);
      chrome.windows.remove(record.windowId).catch(() => {});
    }
    respond({ok: true});
  }
});
chrome.alarms.create("reconnect", {periodInMinutes: 0.5});
chrome.alarms.onAlarm.addListener(async () => {
  await connect();
  for (const [tabId, record] of owners) {
    if (Date.now() - record.lastUsed > IDLE_MS) {
      send({event: "detached", owner: record.owner, tab: String(tabId), reason: "idle"});
      await release(record.owner);
    }
  }
});
setInterval(() => send({ping: true}), 20000);
connect();
