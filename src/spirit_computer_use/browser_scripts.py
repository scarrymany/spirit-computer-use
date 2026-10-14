"""Fixed page helpers. User-supplied JavaScript uses a separate approval path."""

HIT_TEST = """function(x, y, left, top) {
    const rect = this.getBoundingClientRect();
    x = x - left + rect.x;
    y = y - top + rect.y;
    let element = this.ownerDocument.elementFromPoint(x, y);
    while (element?.shadowRoot?.elementFromPoint) {
        const next = element.shadowRoot.elementFromPoint(x, y);
        if (next === element) break;
        element = next;
    }
    return {
        ok: element === this || this.contains(element),
        blocker: element?.outerHTML?.slice(0, 300)
    };
}"""

TARGET_INFO = """function() {
    const element = this.closest?.('button,a,input,[role=button]') || this;
    return {
        password: element.type === 'password',
        submit: element.type === 'submit',
        label: (element.innerText || element.getAttribute?.('aria-label') ||
            element.value || '').slice(0, 200)
    };
}"""

SCROLL_INFO = """function() {
    this.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});
    return {
        password: this.type === 'password', type: this.type,
        disabled: !!this.disabled, connected: this.isConnected
    };
}"""

FOCUS_INFO = """function() {
    let element = this.ownerDocument.activeElement;
    while (element?.shadowRoot?.activeElement) element = element.shadowRoot.activeElement;
    return {
        password: element?.type === 'password',
        editable: element === this && (element.isContentEditable ||
            ['INPUT', 'TEXTAREA'].includes(element.tagName))
    };
}"""

SELECT_OPTION = """function(value) {
    const options = [...this.options].filter(
        option => option.value === value || option.text === value
    );
    if (options.length !== 1) throw Error('Option is missing or ambiguous');
    this.value = options[0].value;
    this.dispatchEvent(new Event('input', {bubbles: true}));
    this.dispatchEvent(new Event('change', {bubbles: true}));
    return this.value;
}"""
