async function refresh() {
  const state = await chrome.runtime.sendMessage({action: "status"});
  document.getElementById("status").textContent = state.connected ? `Connected - ${state.tabs} controlled tabs` : state.error;
}
document.getElementById("connect").onclick = async () => {
  await chrome.runtime.sendMessage({action: "connect"});
  setTimeout(refresh, 500);
};
document.getElementById("stop").onclick = async () => {
  await chrome.runtime.sendMessage({action: "stop"});
  await refresh();
};
refresh();
let tabs=[];
function renderTabs() {
  const query=document.getElementById('search').value.toLowerCase().replace(/^@/,'');
  const list=document.getElementById('tabs');list.replaceChildren();
  for(const tab of tabs.filter(t=>(t.title+' '+t.url).toLowerCase().includes(query))) {
    const button=document.createElement('button');button.className='tab';
    const title=document.createElement('strong');title.textContent=tab.title || tab.url;
    const url=document.createElement('small');url.textContent=tab.url;
    button.append(title,url);button.onclick=async()=>{
      await navigator.clipboard.writeText('@spirit-tab:'+tab.id);
      document.getElementById('copied').textContent='Copied @spirit-tab:'+tab.id+' - paste it into your agent.';
    };list.append(button);
  }
}
chrome.runtime.sendMessage({action:'tabs'}).then(result=>{tabs=result;renderTabs();});
document.getElementById('search').oninput=renderTabs;
