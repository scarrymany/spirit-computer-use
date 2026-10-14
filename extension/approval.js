const id = new URLSearchParams(location.search).get("id");
chrome.runtime.sendMessage({action: "approval", id}).then(result => {
  document.getElementById("message").textContent = result.message;
});
for (const [name, allow] of [["allow", true], ["deny", false]]) {
  document.getElementById(name).onclick = () => chrome.runtime.sendMessage({action: "decide", id, allow});
}
