(() => {
  if (window.top !== window || document.getElementById('__spirit_overlay__')) return;
  const mount = () => {
    if (!document.documentElement || document.getElementById('__spirit_overlay__')) return;
    const host = document.createElement('div');
    host.id = '__spirit_overlay__';
    host.setAttribute('aria-hidden', 'true');
    host.style.cssText = 'all:initial!important;position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;contain:strict!important;';
    const root = host.attachShadow({mode:'closed'});
    root.innerHTML = `<style>
      :host,*{pointer-events:none!important;box-sizing:border-box}
      .frame{position:absolute;inset:2px;border:2px solid #a78bfa88;border-radius:8px}
      .label{position:absolute;top:8px;right:10px;font:11px/1.2 system-ui;letter-spacing:.08em;background:#211b35e8;color:#d9caff;border:1px solid #a78bfa66;border-radius:5px;padding:5px 8px}
      button.stop{pointer-events:auto!important;cursor:pointer;background:transparent;color:#67e8f9;border:0;font:inherit;margin-left:8px}
      .pointer{position:absolute;left:0;top:0;will-change:transform;opacity:0;transition:opacity .2s;filter:drop-shadow(0 1px 2px #0008) drop-shadow(0 0 4px #a78bfa33)}
      .ring{position:absolute;width:38px;height:38px;left:-19px;top:-19px;border:2px solid #67e8f9;border-radius:50%;opacity:0}
      .target{position:absolute;border:2px solid #67e8f9;border-radius:4px;box-shadow:0 0 0 3px #67e8f933;opacity:0}
      .click{animation:pulse .55s ease-out}@keyframes pulse{0%{transform:scale(.3);opacity:1}100%{transform:scale(1.5);opacity:0}}
      @media(prefers-reduced-motion:reduce){.click{animation:none}.pointer{transition:none}}
    </style><div class="frame"></div><div class="label">SPIRIT работает<button class="stop">Стоп</button></div><div class="target"></div>
    <div class="pointer"><div class="ring"></div><svg width="26" height="34" viewBox="0 0 26 34" style="display:block;transform:translate(-2px,-2px)"><path d="M2 2L2 25L8.5 18.5L13 29L17.5 27L13 16.5L22 16.5Z" fill="#f8f5ff" stroke="#9273c9" stroke-width="1.2" stroke-linejoin="round"/></svg></div>`;
    const pointer = root.querySelector('.pointer');
    const ring = root.querySelector('.ring');
    const target = root.querySelector('.target');
    root.querySelector('.stop').onclick = () => globalThis.__spiritStop?.();
    let timer;
    host.spiritMove = ({x, y, click, box}) => {
      pointer.style.transform = `translate(${x}px,${y}px)`;
      pointer.style.opacity = '1';
      if (click) {ring.classList.remove('click'); void ring.offsetWidth; ring.classList.add('click');}
      if (box) {
        Object.assign(target.style, {left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px',opacity:'1'});
      }
      clearTimeout(timer);
      timer = setTimeout(() => {pointer.style.opacity='0';target.style.opacity='0';}, 1800);
    };
    document.documentElement.append(host);
  };
  mount();
  if (!document.documentElement) addEventListener('DOMContentLoaded', mount, {once:true});
})();
