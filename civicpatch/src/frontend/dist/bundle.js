import{registerCivMap as t}from'@components';
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const e=globalThis,s=e.trustedTypes,i=s?s.createPolicy('lit-html',{createHTML:t=>t}):void 0,o='$lit$',n=`lit$${Math.random().toFixed(9).slice(2)}$`,r='?'+n,a=`<${r}>`,l=document,c=()=>l.createComment(''),d=t=>null===t||'object'!=typeof t&&'function'!=typeof t,u=Array.isArray,h='[ \t\n\f\r]',p=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,m=/-->/g,f=/>/g,$=RegExp(`>|${h}(?:([^\\s"'>=/]+)(${h}*=${h}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,'g'),g=/'/g,b=/"/g,v=/^(?:script|style|textarea|title)$/i,_=(t=>(e,...s)=>({_$litType$:t,strings:e,values:s}))(1),y=Symbol.for('lit-noChange'),A=Symbol.for('lit-nothing'),w=new WeakMap,S=l.createTreeWalker(l,129);function E(t,e){if(!u(t)||!t.hasOwnProperty('raw'))throw Error('invalid template strings array');return void 0!==i?i.createHTML(e):e}const C=(t,e)=>{const s=t.length-1,i=[];let r,l=2===e?'<svg>':3===e?'<math>':'',c=p;for(let e=0;e<s;e++){const s=t[e];let d,u,h=-1,_=0;for(;_<s.length&&(c.lastIndex=_,u=c.exec(s),null!==u);)_=c.lastIndex,c===p?'!--'===u[1]?c=m:void 0!==u[1]?c=f:void 0!==u[2]?(v.test(u[2])&&(r=RegExp('</'+u[2],'g')),c=$):void 0!==u[3]&&(c=$):c===$?'>'===u[0]?(c=r??p,h=-1):void 0===u[1]?h=-2:(h=c.lastIndex-u[2].length,d=u[1],c=void 0===u[3]?$:'"'===u[3]?b:g):c===b||c===g?c=$:c===m||c===f?c=p:(c=$,r=void 0);const y=c===$&&t[e+1].startsWith('/>')?' ':'';l+=c===p?s+a:h>=0?(i.push(d),s.slice(0,h)+o+s.slice(h)+n+y):s+n+(-2===h?e:y)}return[E(t,l+(t[s]||'<?>')+(2===e?'</svg>':3===e?'</math>':'')),i]};class x{constructor({strings:t,_$litType$:e},i){let a;this.parts=[];let l=0,d=0;const u=t.length-1,h=this.parts,[p,m]=C(t,e);if(this.el=x.createElement(p,i),S.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(a=S.nextNode())&&h.length<u;){if(1===a.nodeType){if(a.hasAttributes())for(const t of a.getAttributeNames())if(t.endsWith(o)){const e=m[d++],s=a.getAttribute(t).split(n),i=/([.?@])?(.*)/.exec(e);h.push({type:1,index:l,name:i[2],strings:s,ctor:'.'===i[1]?U:'?'===i[1]?M:'@'===i[1]?R:O}),a.removeAttribute(t)}else t.startsWith(n)&&(h.push({type:6,index:l}),a.removeAttribute(t));if(v.test(a.tagName)){const t=a.textContent.split(n),e=t.length-1;if(e>0){a.textContent=s?s.emptyScript:'';for(let s=0;s<e;s++)a.append(t[s],c()),S.nextNode(),h.push({type:2,index:++l});a.append(t[e],c())}}}else if(8===a.nodeType)if(a.data===r)h.push({type:2,index:l});else{let t=-1;for(;-1!==(t=a.data.indexOf(n,t+1));)h.push({type:7,index:l}),t+=n.length-1}l++}}static createElement(t,e){const s=l.createElement('template');return s.innerHTML=t,s}}function k(t,e,s=t,i){if(e===y)return e;let o=void 0!==i?s._$Co?.[i]:s._$Cl;const n=d(e)?void 0:e._$litDirective$;return o?.constructor!==n&&(o?._$AO?.(!1),void 0===n?o=void 0:(o=new n(t),o._$AT(t,s,i)),void 0!==i?(s._$Co??=[])[i]=o:s._$Cl=o),void 0!==o&&(e=k(t,o._$AS(t,e.values),o,i)),e}class P{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??l).importNode(e,!0);S.currentNode=i;let o=S.nextNode(),n=0,r=0,a=s[0];for(;void 0!==a;){if(n===a.index){let e;2===a.type?e=new j(o,o.nextSibling,this,t):1===a.type?e=new a.ctor(o,a.name,a.strings,this,t):6===a.type&&(e=new N(o,this,t)),this._$AV.push(e),a=s[++r]}n!==a?.index&&(o=S.nextNode(),n++)}return S.currentNode=l,i}p(t){let e=0;for(const s of this._$AV)void 0!==s&&(void 0!==s.strings?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}}class j{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=A,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=k(this,t,e),d(t)?t===A||null==t||''===t?(this._$AH!==A&&this._$AR(),this._$AH=A):t!==this._$AH&&t!==y&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>u(t)||'function'==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==A&&d(this._$AH)?this._$AA.nextSibling.data=t:this.T(l.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:s}=t,i='number'==typeof s?this._$AC(t):(void 0===s.el&&(s.el=x.createElement(E(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{const t=new P(i,this),s=t.u(this.options);t.p(e),this.T(s),this._$AH=t}}_$AC(t){let e=w.get(t.strings);return void 0===e&&w.set(t.strings,e=new x(t)),e}k(t){u(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let s,i=0;for(const o of t)i===e.length?e.push(s=new j(this.O(c()),this.O(c()),this,this.options)):s=e[i],s._$AI(o),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class O{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,o){this.type=1,this._$AH=A,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=o,s.length>2||''!==s[0]||''!==s[1]?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=A}_$AI(t,e=this,s,i){const o=this.strings;let n=!1;if(void 0===o)t=k(this,t,e,0),n=!d(t)||t!==this._$AH&&t!==y,n&&(this._$AH=t);else{const i=t;let r,a;for(t=o[0],r=0;r<o.length-1;r++)a=k(this,i[s+r],e,r),a===y&&(a=this._$AH[r]),n||=!d(a)||a!==this._$AH[r],a===A?t=A:t!==A&&(t+=(a??'')+o[r+1]),this._$AH[r]=a}n&&!i&&this.j(t)}j(t){t===A?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??'')}}class U extends O{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===A?void 0:t}}class M extends O{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==A)}}class R extends O{constructor(t,e,s,i,o){super(t,e,s,i,o),this.type=5}_$AI(t,e=this){if((t=k(this,t,e,0)??A)===y)return;const s=this._$AH,i=t===A&&s!==A||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==A&&(s===A||i);i&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){'function'==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class N{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){k(this,t)}}const T=e.litHtmlPolyfillSupport;T?.(x,j),(e.litHtmlVersions??=[]).push('3.3.1');const D=(t,e,s)=>{const i=s?.renderBefore??e;let o=i._$litPart$;if(void 0===o){const t=s?.renderBefore??null;i._$litPart$=o=new j(e.insertBefore(c(),t),t,void 0,s??{})}return o._$AI(t),o};let L,H=0;function z(t){L=t}function I(){L=null,H=0}const B=Symbol('haunted.phase'),V=Symbol('haunted.hook'),W=Symbol('haunted.update'),G=Symbol('haunted.commit'),q=Symbol('haunted.effects'),J=Symbol('haunted.layoutEffects'),Q='haunted.context';class F{update;host;virtual;[V];[q];[J];constructor(t,e){this.update=t,this.host=e,this[V]=new Map,this[q]=[],this[J]=[]}run(t){z(this);let e=t();return I(),e}_runEffects(t){let e=this[t];z(this);for(let t of e)t.call(this);I()}runEffects(){this._runEffects(q)}runLayoutEffects(){this._runEffects(J)}teardown(){this[V].forEach(t=>{'function'==typeof t.teardown&&t.teardown()})}}const Z=Promise.resolve().then.bind(Promise.resolve());function K(){let t,e=[];function s(){t=null;let s=e;e=[];for(var i=0,o=s.length;i<o;i++)s[i]()}return i=>{e.push(i),null==t&&(t=Z(s))}}const Y=K(),X=K();class tt{renderer;host;state;[B];_updateQueued;constructor(t,e){this.renderer=t,this.host=e,this.state=new F(this.update.bind(this),e),this[B]=null,this._updateQueued=!1}update(){this._updateQueued||(Y(()=>{let t=this.handlePhase(W);X(()=>{this.handlePhase(G,t),X(()=>{this.handlePhase(q)})}),this._updateQueued=!1}),this._updateQueued=!0)}handlePhase(t,e){switch(this[B]=t,t){case G:return this.commit(e),void this.runEffects(J);case W:return this.render();case q:return this.runEffects(q)}}render(){return this.state.run(()=>this.renderer.call(this.host,this.host))}runEffects(t){this.state._runEffects(t)}teardown(){this.state.teardown()}}function et(t){class e extends tt{frag;constructor(t,e,s){super(t,s||e),this.frag=e}commit(e){t(e,this.frag)}}return function(t,s,i){const o=(i||s||{}).baseElement||HTMLElement,{observedAttributes:n=[],useShadowDOM:r=!0,shadowRootInit:a={}}=i||s||{};class l extends o{_scheduler;static get observedAttributes(){return t.observedAttributes||n||[]}constructor(){super(),!1===r?this._scheduler=new e(t,this):(this.attachShadow({mode:'open',...a}),this._scheduler=new e(t,this.shadowRoot,this))}connectedCallback(){this._scheduler.update()}disconnectedCallback(){this._scheduler.teardown()}attributeChangedCallback(t,e,s){if(e===s)return;let i=''===s||s;Reflect.set(this,((t='')=>t.replace(/-+([a-z])?/g,(t,e)=>e?e.toUpperCase():''))(t),i)}}const c=new Proxy(o.prototype,{getPrototypeOf:t=>t,set(t,e,s,i){let o;return e in t?(o=Object.getOwnPropertyDescriptor(t,e),o&&o.set?(o.set.call(i,s),!0):(Reflect.set(t,e,s,i),!0)):(o='symbol'==typeof e||'_'===e[0]?{enumerable:!0,configurable:!0,writable:!0,value:s}:function(t){let e=t,s=!1;return Object.freeze({enumerable:!0,configurable:!0,get:()=>e,set(t){s&&e===t||(s=!0,e=t,this._scheduler&&this._scheduler.update())}})}(s),Object.defineProperty(i,e,o),o.set&&o.set.call(i,s),!0)}});return Object.setPrototypeOf(l.prototype,c),l}}class st{id;state;constructor(t,e){this.id=t,this.state=e}}function it(t,...e){let s=H++,i=L[V],o=i.get(s);return o||(o=new t(s,L,...e),i.set(s,o)),o.update(...e)}function ot(t){return it.bind(null,t)}function nt(t){return ot(class extends st{callback;lastValues;values;_teardown;constructor(e,s,i,o){super(e,s),t(s,this)}update(t,e){this.callback=t,this.values=e}call(){const t=!this.values||this.hasChanged();this.lastValues=this.values,t&&this.run()}run(){this.teardown(),this._teardown=this.callback.call(this.state)}teardown(){'function'==typeof this._teardown&&this._teardown()}hasChanged(){return!this.lastValues||this.values.some((t,e)=>this.lastValues[e]!==t)}})}function rt(t,e){t[q].push(e)}const at=nt(rt),lt=ot(class extends st{Context;value;_ranEffect;_unsubscribe;constructor(t,e,s){super(t,e),this._updater=this._updater.bind(this),this._ranEffect=!1,this._unsubscribe=null,rt(e,this)}update(t){if(this.state.virtual)throw new Error('can\'t be used with virtual components');return this.Context!==t&&(this._subscribe(t),this.Context=t),this.value}call(){this._ranEffect||(this._ranEffect=!0,this._unsubscribe&&this._unsubscribe(),this._subscribe(this.Context),this.state.update())}_updater(t){this.value=t,this.state.update()}_subscribe(t){const e={Context:t,callback:this._updater};this.state.host.dispatchEvent(new CustomEvent(Q,{detail:e,bubbles:!0,cancelable:!0,composed:!0}));const{unsubscribe:s=null,value:i}=e;this.value=s?i:t.defaultValue,this._unsubscribe=s}teardown(){this._unsubscribe&&this._unsubscribe()}});const ct=ot(class extends st{value;values;constructor(t,e,s,i){super(t,e),this.value=s(),this.values=i}update(t,e){return this.hasChanged(e)&&(this.values=e,this.value=t()),this.value}hasChanged(t=[]){return t.some((t,e)=>this.values[e]!==t)}});nt(function(t,e){t[J].push(e)});const dt=ot(class extends st{args;constructor(t,e,s){if(super(t,e),this.updater=this.updater.bind(this),'function'==typeof s){s=s()}this.makeArgs(s)}update(){return this.args}updater(t){const[e]=this.args;if('function'==typeof t){t=t(e)}Object.is(e,t)||(this.makeArgs(t),this.state.update())}makeArgs(t){this.args=Object.freeze([t,this.updater])}});
/**
 * @license
 * Portions Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Promise.resolve(),ot(class extends st{reducer;currentState;constructor(t,e,s,i,o){super(t,e),this.dispatch=this.dispatch.bind(this),this.currentState=void 0!==o?o(i):i}update(t){return this.reducer=t,[this.currentState,this.dispatch]}dispatch(t){this.currentState=this.reducer(this.currentState,t),this.state.update()}});
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ut=2;let ht=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,s){this._$Ct=t,this._$AM=e,this._$Ci=s}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */const pt=globalThis,mt=pt.ShadowRoot&&(void 0===pt.ShadyCSS||pt.ShadyCSS.nativeShadow)&&'adoptedStyleSheets'in Document.prototype&&'replace'in CSSStyleSheet.prototype,ft=Symbol(),$t=new WeakMap;let gt=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==ft)throw Error('CSSResult is not constructable. Use `unsafeCSS` or `css` instead.');this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(mt&&void 0===t){const s=void 0!==e&&1===e.length;s&&(t=$t.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&$t.set(e,t))}return t}toString(){return this.cssText}};const bt=(t,e)=>{if(mt)t.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const s of e){const e=document.createElement('style'),i=pt.litNonce;void 0!==i&&e.setAttribute('nonce',i),e.textContent=s.cssText,t.appendChild(e)}},vt=mt?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e='';for(const s of t.cssRules)e+=s.cssText;return(t=>new gt('string'==typeof t?t:t+'',void 0,ft))(e)})(t):t,{is:_t,defineProperty:yt,getOwnPropertyDescriptor:At,getOwnPropertyNames:wt,getOwnPropertySymbols:St,getPrototypeOf:Et}=Object,Ct=globalThis,xt=Ct.trustedTypes,kt=xt?xt.emptyScript:'',Pt=Ct.reactiveElementPolyfillSupport,jt=(t,e)=>t,Ot={toAttribute(t,e){switch(e){case Boolean:t=t?kt:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let s=t;switch(e){case Boolean:s=null!==t;break;case Number:s=null===t?null:Number(t);break;case Object:case Array:try{s=JSON.parse(t)}catch(t){s=null}}return s}},Ut=(t,e)=>!_t(t,e),Mt={attribute:!0,type:String,converter:Ot,reflect:!1,useDefault:!1,hasChanged:Ut};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol('metadata'),Ct.litPropertyMetadata??=new WeakMap;class Rt extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Mt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const s=Symbol(),i=this.getPropertyDescriptor(t,s,e);void 0!==i&&yt(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){const{get:i,set:o}=At(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:i,set(e){const n=i?.call(this);o?.call(this,e),this.requestUpdate(t,n,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Mt}static _$Ei(){if(this.hasOwnProperty(jt('elementProperties')))return;const t=Et(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(jt('finalized')))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(jt('properties'))){const t=this.properties,e=[...wt(t),...St(t)];for(const s of e)this.createProperty(s,t[s])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,s]of e)this.elementProperties.set(t,s)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const s=this._$Eu(t,e);void 0!==s&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const s=new Set(t.flat(1/0).reverse());for(const t of s)e.unshift(vt(t))}else void 0!==t&&e.push(vt(t));return e}static _$Eu(t,e){const s=e.attribute;return!1===s?void 0:'string'==typeof s?s:'string'==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return bt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){const s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(void 0!==i&&!0===s.reflect){const o=(void 0!==s.converter?.toAttribute?s.converter:Ot).toAttribute(e,s.type);this._$Em=t,null==o?this.removeAttribute(i):this.setAttribute(i,o),this._$Em=null}}_$AK(t,e){const s=this.constructor,i=s._$Eh.get(t);if(void 0!==i&&this._$Em!==i){const t=s.getPropertyOptions(i),o='function'==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:Ot;this._$Em=i;const n=o.fromAttribute(e,t.type);this[i]=n??this._$Ej?.get(i)??n,this._$Em=null}}requestUpdate(t,e,s){if(void 0!==t){const i=this.constructor,o=this[t];if(s??=i.getPropertyOptions(t),!((s.hasChanged??Ut)(o,e)||s.useDefault&&s.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(i._$Eu(t,s))))return;this.C(t,e,s)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:o},n){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),!0!==o||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),!0===i&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,s]of t){const{wrapped:t}=s,i=this[e];!0!==t||this._$AL.has(e)||void 0===i||this.C(e,void 0,s,i)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}}Rt.elementStyles=[],Rt.shadowRootOptions={mode:'open'},Rt[jt('elementProperties')]=new Map,Rt[jt('finalized')]=new Map,Pt?.({ReactiveElement:Rt}),(Ct.reactiveElementVersions??=[]).push('2.1.1');
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Nt=globalThis;class Tt extends Rt{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=D(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return y}}Tt._$litElement$=!0,Tt.finalized=!0,Nt.litElementHydrateSupport?.({LitElement:Tt});const Dt=Nt.litElementPolyfillSupport;Dt?.({LitElement:Tt}),(Nt.litElementVersions??=[]).push('4.2.1');
/**
 * @license
 * Copyright 2020 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Lt=(t,e)=>{const s=t._$AN;if(void 0===s)return!1;for(const t of s)t._$AO?.(e,!1),Lt(t,e);return!0},Ht=t=>{let e,s;do{if(void 0===(e=t._$AM))break;s=e._$AN,s.delete(t),t=e}while(0===s?.size)},zt=t=>{for(let e;e=t._$AM;t=e){let s=e._$AN;if(void 0===s)e._$AN=s=new Set;else if(s.has(t))break;s.add(t),Vt(e)}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function It(t){void 0!==this._$AN?(Ht(this),this._$AM=t,zt(this)):this._$AM=t}function Bt(t,e=!1,s=0){const i=this._$AH,o=this._$AN;if(void 0!==o&&0!==o.size)if(e)if(Array.isArray(i))for(let t=s;t<i.length;t++)Lt(i[t],!1),Ht(i[t]);else null!=i&&(Lt(i,!1),Ht(i));else Lt(this,t)}const Vt=t=>{t.type==ut&&(t._$AP??=Bt,t._$AQ??=It)};class Wt extends ht{constructor(){super(...arguments),this._$AN=void 0}_$AT(t,e,s){super._$AT(t,e,s),zt(this),this.isConnected=t._$AU}_$AO(t,e=!0){t!==this.isConnected&&(this.isConnected=t,t?this.reconnected?.():this.disconnected?.()),e&&(Lt(this,t),Ht(this))}setValue(t){if((t=>void 0===t.strings)(this._$Ct))this._$Ct._$AI(t,this);else{const e=[...this._$Ct._$AH];e[this._$Ci]=t,this._$Ct._$AI(e,this,0)}}disconnected(){}reconnected(){}}const{component:Gt}=function({render:t}){const e=et(t),s=function(t){return e=>{const s={Provider:class extends HTMLElement{listeners;_value;constructor(){super(),this.listeners=new Set,this.addEventListener(Q,this)}disconnectedCallback(){this.removeEventListener(Q,this)}handleEvent(t){const{detail:e}=t;e.Context===s&&(e.value=this.value,e.unsubscribe=this.unsubscribe.bind(this,e.callback),this.listeners.add(e.callback),t.stopPropagation())}unsubscribe(t){this.listeners.delete(t)}set value(t){this._value=t;for(let e of this.listeners)e(t)}get value(){return this._value}},Consumer:t(({render:t})=>t(lt(s)),{useShadowDOM:!1}),defaultValue:e};return s}}(e);return{component:e,createContext:s}}({render:D});
/**
 * @license
 * Copyright 2020 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class qt{}const Jt=new WeakMap,Qt=(t=>(...e)=>({_$litDirective$:t,values:e}))(class extends Wt{render(t){return A}update(t,[e]){const s=e!==this.G;return s&&void 0!==this.G&&this.rt(void 0),(s||this.lt!==this.ct)&&(this.G=e,this.ht=t.options?.host,this.rt(this.ct=t.element)),A}rt(t){if(this.isConnected||(t=void 0),'function'==typeof this.G){const e=this.ht??globalThis;let s=Jt.get(e);void 0===s&&(s=new WeakMap,Jt.set(e,s)),void 0!==s.get(this.G)&&this.G.call(this.ht,void 0),s.set(this.G,t),void 0!==t&&this.G.call(this.ht,t)}else this.G.value=t}get lt(){return'function'==typeof this.G?Jt.get(this.ht??globalThis)?.get(this.G):this.G?.value}disconnected(){this.lt===this.ct&&this.rt(void 0)}reconnected(){this.rt(this.ct)}});customElements.define('civ-autocomplete-select',Gt(function({disabled:t,optionsMetadata:e={},options:s=[],label:i='Search',inputValue:o='',pageSize:n=25}){const[r,a]=dt(null),[l,c]=dt(-1),[d,u]=dt(!1),[h,p]=dt(null),[m,f]=dt(1);at(()=>{o||a(null)},[o]),at(()=>{l>=0&&A()},[l]);const $=(t,e=1)=>{const s=t||'';this.dispatchEvent(new CustomEvent('fetch-suggestions',{detail:{query:s,page:e,pageSize:n},bubbles:!0,composed:!0})),c(-1),f(e)},g=ct(()=>((t,e)=>{let s;return(...i)=>{s&&clearTimeout(s),s=setTimeout(()=>{t.apply(null,i)},e)}})($,300),[]),b=t=>{a(t),u(!1),f(1),h&&h.focus(),this.dispatchEvent(new CustomEvent('item-selected',{detail:t,bubbles:!0,composed:!0})),this.dispatchEvent(new CustomEvent('input-change',{detail:{value:t.label,item:t},bubbles:!0,composed:!0}))},v=e?.links?.prev,y=e?.links?.next,A=t=>{setTimeout(()=>{const t=this.querySelector('.autocomplete-option[aria-selected="true"]');t&&t.scrollIntoView({behavior:'smooth',block:'nearest'})},0)};return _`
    <style>
      .autocomplete-wrapper {
        position: relative;
        width: 100%;
      }

      .autocomplete-wrapper fieldset.grid {
        margin-bottom: 0;
        gap: 0;
      }

      .autocomplete-input {
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
        margin-bottom: 0;
      }

      .autocomplete-toggle {
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        padding: 0.5rem 0.75rem;
        min-width: 3rem;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0;
      }

      .autocomplete-dropdown {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: var(--pico-background-color);
        border: var(--pico-border-width) solid var(--pico-muted-border-color);
        border-radius: var(--pico-border-radius);
        margin-top: 0.25rem;
        max-height: 400px;
        z-index: 99;
        box-shadow: var(--pico-box-shadow);
        display: flex;
        flex-direction: column;
      }

      .autocomplete-options {
        flex: 1;
        overflow-y: auto;
        list-style: none;
        margin: 0;
        padding: 0;
      }

      .autocomplete-option {
        padding: 0.75rem 1rem;
        cursor: pointer;
        border-bottom: 1px solid var(--pico-muted-border-color);
        transition: background-color 0.1s ease;
        list-style: none;
      }

      .autocomplete-option:last-child {
        border-bottom: none;
      }

      .autocomplete-option:hover,
      .autocomplete-option.active {
        background-color: var(--pico-secondary-background);
      }

      .autocomplete-option[aria-selected="true"] {
        background-color: var(--pico-primary-background);
        color: var(--pico-primary-inverse);
      }

      .autocomplete-pagination {
        border-top: 1px solid var(--pico-muted-border-color);
        padding: 0.75rem 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--pico-card-background-color);
        border-radius: 0 0 var(--pico-border-radius) var(--pico-border-radius);
      }

      .autocomplete-pagination-info {
        font-size: 0.875rem;
        color: var(--pico-muted-color);
      }

      .autocomplete-pagination-controls {
        display: flex;
        gap: 0.5rem;
      }

      .autocomplete-pagination button {
        padding: 0.25rem 0.75rem;
        font-size: 0.875rem;
        margin: 0;
      }

      .autocomplete-pagination button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .autocomplete-selected {
        display: block;
        margin-top: 0.5rem;
        color: var(--pico-muted-color);
      }
    </style> 

        <label class="visually-hidden">${i}</label>
    <div class="autocomplete-wrapper">
      <fieldset class="grid" role="group">
        <input 
          class="autocomplete-input" 
          type="text" 
          role="combobox" 
          aria-autocomplete="both" 
          aria-expanded=${d?'true':'false'}
          aria-label=${i}
          .value=${o}
          @input=${t=>{const e=t.target.value;a(null),f(1),this.dispatchEvent(new CustomEvent('input-change',{detail:{value:e,item:null},bubbles:!0,composed:!0})),g(e)}}
          @keydown=${t=>{if(0!==s.length)switch(t.key){case'ArrowDown':t.preventDefault(),u(!0),c(t=>(t+1)%s.length);break;case'ArrowUp':t.preventDefault(),u(!0),c(t=>(t-1+s.length)%s.length);break;case'Enter':l>=0&&d&&(t.preventDefault(),b(s[l]));break;case'Escape':u(!1)}}}
          @blur=${()=>u(!1)}
          @focus=${()=>u(!0)}
          ${Qt(p)}
        >
        
        <button 
          type="button" 
          class="autocomplete-toggle"
          aria-label="Toggle suggestions list" 
          aria-expanded=${d?'true':'false'}
          tabindex="-1"
          @click=${()=>{const t=!d;u(t),t&&h&&h.focus()}}
        >
          <svg width="18" height="16" aria-hidden="true" focusable="false">
            <polygon 
              class="arrow" 
              stroke-width="0" 
              fill-opacity="0.75" 
              fill="currentcolor" 
              points="3,6 15,6 9,14"
              style="transform: rotate(${d?'180deg':'0deg'}); transform-origin: 50% 50%; transition: transform 0.2s;"
            ></polygon>
          </svg>
        </button>
      </fieldset>
      
      ${d&&s.length>0?_`
        <div class="autocomplete-dropdown">
          <ul 
            role="listbox" 
            aria-label=${i}
            class="autocomplete-options"
          >
            ${s.map((t,e)=>_`
              <li 
                role="option"
                aria-selected=${e===l?'true':'false'}
                @mousedown=${e=>{e.preventDefault(),(t=>{b(t)})(t)}}
                @mouseover=${()=>c(e)}
                class="autocomplete-option ${e===l?'active':''}"
              >
                ${t.label}
              </li>
            `)}
          </ul>
          
          ${e?.total_items>n?_`
            <div class="autocomplete-pagination">
              <span class="autocomplete-pagination-info">
                Showing ${e?.page}-${e?.total_pages} of ${e?.total_items}
              </span>
              <div class="autocomplete-pagination-controls">
                <button 
                  type="button"
                  @mousedown=${t=>{t.preventDefault(),v&&$(o,m-1)}}
                  ?disabled=${!v}
                  aria-label="Previous page"
                >
                  Previous
                </button>
                <button 
                  type="button"
                  @mousedown=${t=>{t.preventDefault(),y&&$(o,m+1)}}
                  ?disabled=${!y}
                  aria-label="Next page"
                >
                  Next
                </button>
              </div>
            </div>
          `:''}
        </div>
      `:''}
      
      ${r?_`<small class="autocomplete-selected">Selected: ${r.label}</small>`:''}
    </div>
  `},{useShadowDOM:!1})),customElements.define('civ-people-list',Gt(function({local:t=[]}){const e=t;return e&&0!==e.length?_`
    <figure>
        <table role="grid">
            <thead>
                <tr>
                    <th style="width: 1%;">Photo</th>
                    <th style="width: 15%;">Official</th>
                    <th style="width: 15%">Contact</th>
                </tr>
            </thead>
            <tbody>
                ${e.map(t=>_`
                    <tr>
                        <td data-label="Photo">
                            ${t.cdn_image||t.image?_`
                                <img 
                                    src="${t.cdn_image||t.image}" 
                                    alt="Photo of ${t.name}" 
                                    style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover;"
                                    
                                    onerror="this.onerror=null; this.style.display='none'; this.closest('td').querySelector('.fallback-icon').style.display='inline-block';"
                                >
                                <span class="fallback-icon" style="display: none; width: 50px; height: 50px; line-height: 50px; text-align: center; border-radius: 50%; background: var(--pico-muted-border-color); color: var(--pico-secondary-hover-color);">👤</span>
                            `:_`<span class="fallback-icon" style="width: 50px; height: 50px; line-height: 50px; text-align: center; border-radius: 50%; background: var(--pico-muted-border-color); color: var(--pico-secondary-hover-color); display: inline-block;">👤</span>`}
                        </td>
                        
                        <td data-label="Official">
                            <strong>${t.name}</strong>
                            <small style="display: block;">${t.office&&t.office.name}</small>
                            <small style="display: block;">${(t=>(t=>{const e=t.office.division_ocdid||'';return!(!e.includes('district')&&!e.includes('ward'))})(t)?`${(t=>{const e=(t.office.division_ocdid||'').split('/');for(const t of e){if(t.startsWith('council_district:'))return`District ${t.split(':')[1]}`;if(t.startsWith('ward:'))return`Ward ${t.split(':')[1]}`}})(t)}`:null)(t)}</small>
                        </td>

                        <td data-label="Contact">
                            ${t.emails?_`<a href="mailto:${t.emails.join(',')}" style="display: block;">${t.emails.join(',')}</a>`:''}
                            ${t.phones?_`<a href="tel:${t.phones.join(',')}" style="display: block;">${t.phones.join(',')}</a>`:''}
                            ${t.urls?_`<a href="${t.urls.join(',')}" target="_blank" class="secondary">Link</a>`:''}
                        </td>
                    </tr>
                `)}
            </tbody>
        </table>
    </figure>
    `:_`<p role="alert">No people data available for this jurisdiction.</p>`},{useShadowDOM:!1,observedAttributes:[]})),customElements.define('civ-modal',Gt(function({title:t='',content:e=null,footer:s=null,modalProps:i={}}){const[o,n]=dt(Boolean(i.open));at(()=>{n(Boolean(i.open))},[i.open]);let r=null;return at(()=>{o&&r&&'function'==typeof r.focus&&r.focus()},[o]),_`
    <dialog
      ?open=${o}
      tabindex="-1"
      aria-label=${i.ariaLabel||t||'Modal'}
      @click=${t=>{(i.closeOnBackdropClick||void 0===i.closeOnBackdropClick)&&t.target&&t.target.tagName&&'dialog'===t.target.tagName.toLowerCase()&&i.onClose&&i.onClose()}}
      @keydown=${t=>{'Escape'===t.key&&i.onClose&&i.onClose()}}
      ${Qt(t=>{r=t,i.modalRef&&('function'==typeof i.modalRef?i.modalRef(t):'object'==typeof i.modalRef&&(i.modalRef.value=t))})}
    >
      <article @click=${t=>t.stopPropagation()}>
        ${t?_`
              <header>
                <h2>${t}</h2>
              </header>
            `:null}

        <section>
          ${e}
        </section>

        ${s?_` <footer>${s}</footer> `:_`
              <footer>
                <button @click=${i.onClose} class="secondary">Close</button>
              </footer>
            `}
      </article>
    </dialog>
  `},{useShadowDOM:!1}));const Ft=[{id:1,name:'Scrape Job 1',status:'Completed',start_date:'2024-01-01',duration_in_s:120,source_urls:['https://example.com','https://example.com/2'],progress:100},{id:2,name:'Scrape Job 2',status:'In Progress',start_date:'2024-01-02',duration_in_s:150,source_urls:['https://example.org'],progress:50},{id:3,name:'Scrape Job 3',status:'Failed',start_date:'2024-01-03',duration_in_s:90,source_urls:[],progress:0}];customElements.define('civ-scrape-history-list',Gt(function(){const t=Ft,[e,s]=dt(!1),[i,o]=dt(null),n=t=>{if(!t)return'';const e=new Date(t);return isNaN(e)?String(t):`${String(e.getMonth()+1).padStart(2,'0')}/${String(e.getDate()).padStart(2,'0')}/${e.getFullYear()}`},r=i?_`<div>
        <p><strong>Date / Time:</strong> ${n(i.start_date)}</p>
        <p><strong>Status:</strong> ${i.status}</p>
        <p><strong>Time to scrape:</strong> ${i.duration_in_s}s</p>
        <p><strong>URLs scraped:</strong></p>
        <ul>
          ${i.source_urls&&i.source_urls.length>0?i.source_urls.map(t=>_`<li><a href="${t}" target="_blank" rel="noopener">${t}</a></li>`):_`<li><em>No source URLs</em></li>`}
        </ul>
      </div>`:null;return t&&0!==t.length?_`
    <style>
      ul.list { padding: 0; margin: 0; }
      ul li { list-style: none; margin: 0; }
      .item { padding: 0.5rem 0; }
      .row { display: grid; grid-template-columns: 1fr auto; gap: 0.75rem; align-items: center; }
      .btn { all: unset; cursor: pointer; text-decoration: underline; display: inline-block; }
      .pill { font-weight: 600; padding: 0.25rem 0.5rem; border-radius: 999px; background: rgba(0,0,0,0.04); font-size: 0.9rem; }
      .pill.completed { background: #e6f9ea; color: #117a2d; }
      .pill.in-progress { background: #fff7e6; color: #99660b; }
      .pill.failed { background: #ffecec; color: #9b1f1f; }
    </style>

    <ul class="list">
      ${
/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
function*(t,e){if(void 0!==t){let s=0;for(const i of t)yield e(i,s++)}}(t,t=>{const e=t.status?t.status.toLowerCase().replace(/\s+/g,'-'):'';return _`
            <li class="item">
              <div class="row">
                <button class="btn" @click=${()=>(t=>{o(t),s(!0)})(t)}>
                  ${n(t.start_date)}
                </button>
                <div><span class="pill ${e}">${t.status}</span></div>
              </div>
            </li>
          `})}
    </ul>

    <hr />

    <civ-modal
      .title=${'Scrape Details'}
      .content=${r}
      .modalProps=${{open:e,onClose:()=>{s(!1),o(null)},closeOnBackdropClick:!0}}
    ></civ-modal>
  `:_`<p>No scrape history available.</p>`},{useShadowDOM:!1}));const Zt={created_at:'2024-06-01T12:00:00Z',status:'Accepted',duration_in_s:360,source_urls:['https://example.com','https://example.org']};function Kt(t=!1){const[e,s]=dt(t),i=new qt,o=()=>s(!1);return at(()=>{e&&i.value&&i.value.focus()},[e]),at(()=>{const t=t=>{'Escape'===t.key&&e&&o()};if(e)return document.addEventListener('keydown',t),()=>{document.removeEventListener('keydown',t)}},[e,o]),at(()=>{const t=t=>{i.value&&!i.value.contains(t.target)&&e&&o()};if(e)return document.addEventListener('mousedown',t),()=>{document.removeEventListener('mousedown',t)}},[e,o]),{isOpen:e,openModal:()=>s(!0),closeModal:o,modalProps:{open:e,onClose:o,modalRef:i}}}customElements.define('scrape-details',Gt(function({detail:t=Zt}){const e=t?.created_at?new Date(t.created_at):null,s=e?e.toLocaleString():'',i=function(t){if(null==t)return'';const e=Math.floor(t/3600),s=Math.floor(t%3600/60);return[e?`${e}h`:null,s?`${s}m`:null,t%60+'s'].filter(Boolean).join(' ')}(t?.duration_in_s),o=t?.source_urls||[];return _`
    <article class="container">
      <form>
        <div class="grid">
          <label>
            <span>Date / Time</span>
            <input type="text" value="${s}" readonly />
          </label>

          <label>
            <span>Status</span>
            <input type="text" value="${t?.status||''}" readonly />
          </label>

          <label>
            <span>Time to scrape</span>
            <input type="text" value="${i}${null!=t?.duration_in_s?` (${t.duration_in_s}s)`:''}" readonly />
          </label>
        </div>

        <section>
          <h4>URLs scraped</h4>
          ${o.length?_`<ul>
                ${o.map(t=>_`<li><a href="${t}" target="_blank" rel="noopener">${t}</a></li>`)}
              </ul>`:_`<p><em>No source URLs</em></p>`}
        </section>
      </form>
    </article>
    `})),customElements.define('civ-select-jurisdiction',Gt(function(){const[t,e]=dt([]),[s,i]=dt([]),[o,n]=dt({}),[r,a]=dt(''),[l,c]=dt(''),[d,u]=dt(''),h=(p=!0,ct(()=>({current:p}),[]));var p;at(()=>{h.current?h.current=!1:m(r,l)},[r,l]),at(()=>{fetch('/api/api_proxy/jurisdictions/states').then(t=>t.json()).then(t=>e(t.data||[]))},[]),at(()=>{i([]),n({}),c(''),u(''),r&&f('')},[r]);const m=(t,e)=>{this.dispatchEvent(new CustomEvent('select-jurisdiction-change',{detail:{state:t,jurisdiction_ocdid:e},bubbles:!0,composed:!0}))},f=t=>{const e=t.query||'',s=t.page||1,o=t.pageSize||25;fetch(`/api/api_proxy/jurisdictions/${r}/search?search_string=${encodeURIComponent(e)}&limit=${o}&page=${s}`).then(t=>t.json()).then(t=>{i(t.data||[]),n({total_items:t.total_items,total_pages:t.total_pages,page:t.page,limit:t.limit,links:t.links})})};return _`
    <form 
      class="grid" 
      style="grid-template-columns: 2fr; gap: 1rem;"
      onsubmit="return false;"
    >
      <label for="state-select" class="visually-hidden">State:</label>
      <select
        id="state-select"
        .value=${r}
        @change=${t=>a(t.target.value)}
        required
      >
        <option value="">Select a state</option>
        ${t.map(t=>_`<option value=${t}>${t}</option>`)}
      </select>
      <civ-autocomplete-select
        id="jurisdiction-autocomplete"
        .disabled=${!r}
        .inputValue=${d}
        .options=${s.map(t=>({label:t.name,value:t.id}))}
        .optionsMetadata=${o}
        .pageSize=${25}
        @fetch-suggestions=${t=>{const e=t.detail;f(e)}}
        @input-change=${t=>{const{value:e,item:s}=t.detail;u(e),c(s?s.value:'')}}
        @item-selected=${t=>c(t.detail.value)}
      ></civ-autocomplete-select>
      <!-- comment out submit button for now.
      <button 
        type="submit" 
        @click=${t=>{t.preventDefault();const e=s.find(t=>t.id===l).jurisdiction_ocdid_slug;window.location.href=`/jurisdictions/${e}`}} 
        ?disabled=${!l}>Submit</button>
      -->
      <a href="${(()=>{if(!l)return'';if(!s)return'';const t=encodeURIComponent(l);return t?`/jurisdictions?jurisdiction_ocdid=${t}`:''})()}" ?hidden=${!l}>
        Go to jurisdiction page
      </a>
    </form>
  `},{useShadowDOM:!1,observedAttributes:[]})),customElements.define('civ-search-jurisdictions',Gt(function(){const[t,e]=dt(null),[s,i]=dt(null),[o,n]=dt([]),[r,a]=dt([]);at(()=>{if(!s)return;const t=encodeURIComponent(s);fetch(`/api/api_proxy/people?jurisdiction_ocdid=${t}`).then(t=>t.json()).then(t=>{n(t.data)})},[s]);const l=t=>{const{state:s,jurisdiction_ocdid:o}=t.detail;e(s),i(o)};return _`
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div>
          <civ-map
            @on-map-change=${t=>{const{latlng:e,zoom:s}=t.detail;e&&s&&fetch(`/api/api_proxy/jurisdictions/geojson?lat=${e.lat}&long=${e.lng}&zoom=${s}`).then(t=>t.json()).then(t=>{a(t)})}}
            @on-jurisdiction-change=${l}
            .geojson=${r}
          ></civ-map>
        </div>
        <civ-select-jurisdiction
          @select-jurisdiction-change=${l}
        ></civ-select-jurisdiction>
      </div>
      <civ-people-list .local=${o}></civ-people-list>
    </div>

  `},{useShadowDOM:!1,observedAttributes:[]})),customElements.define('name-config-form',Gt(function({onChange:t,existingNameConfigs:e={}}){const[s,i]=dt(Object.entries(e).map(([t,e])=>({canonical:t,alternates:e}))),[o,n]=dt(''),[r,a]=dt('');return at(()=>{const e={};s.forEach(({canonical:t,alternates:s})=>{t.trim()&&(e[t.trim()]=s.filter(t=>t.trim()))}),t(e)},[s]),_`
    <section class="container">
      <label>
        <span>New Identity Name</span>
        <input
          type="text"
          class="input"
          .value=${o}
          @input=${t=>n(t.target.value)}
          placeholder="e.g. Bob A"
        />
      </label>
      <button type="button" class="button" @click=${()=>{o.trim()&&(i([...s,{canonical:o.trim(),alternates:[]}]),n(''))}}>
        Add Identity
      </button>
      <ul class="list" style="list-style: none;">
        ${s.map((t,e)=>_`
            <li class="card" style="list-style: none;">
              <div class="grid">
                <strong>${t.canonical}</strong>
                <button type="button" class="button outline" @click=${()=>(t=>{i(s.filter((e,s)=>s!==t))})(e)}>
                  Remove Identity
                </button>
              </div>
              <ul class="list" style="list-style: none;">
                ${t.alternates.map((t,o)=>_`
                    <li class="grid">
                      <span>${t}</span>
                      <button type="button" class="button outline" @click=${()=>((t,e)=>{const o=[...s];o[t].alternates=o[t].alternates.filter((t,s)=>s!==e),i(o)})(e,o)}>
                        Remove
                      </button>
                    </li>
                  `)}
              </ul>
              <input
                type="text"
                class="input"
                .value=${e===s.length-1?r:''}
                @input=${t=>a(t.target.value)}
                placeholder="Add alternate name"
              />
              <button type="button" class="button" @click=${()=>(t=>{if(r.trim()){const e=[...s];e[t].alternates.push(r.trim()),i(e),a('')}})(e)}>
                Add Alternate
              </button>
            </li>
          `)}
      </ul>
      <small>
        Add identities and their alternate names.<br>
        Example: Identity "Robert Allen" with alternates "Bob A", "Bob B", etc.
      </small>
    </section>
  `},{useShadowDOM:!1})),customElements.define('civ-scrape-modal',Gt(function({onStartScrape:t,url:e='',sourceUrls:s=[],modalProps:i={}}){const[o,n]=dt('top-level-url'),[r,a]=dt(e),[l,c]=dt(s),[d,u]=dt({}),h=t=>{n(t.target.value)},p=t=>{if(!t||''===t.trim())return!1;try{return new URL(t),!0}catch{return!1}},m='top-level-url'===o?p(r):l.length>0&&l.every(t=>p(t));return _`
    <dialog ?open=${i.open} tabindex="-1">
      <article @click=${t=>t.stopPropagation()} ${Qt(i.modalRef)}>
        <header>
          <p><strong>URLs to Scrape</strong></p>
        </header>

        <fieldset>
          <input
            type="radio"
            id="top-level-url"
            name="scrape-scope"
            value="top-level-url"
            ?checked=${'top-level-url'===o}
            @change=${h}
          />
          <label for="top-level-url">Top-level URL only</label>

          <input
            type="radio"
            id="specific-urls"
            name="scrape-scope"
            value="specific-urls"
            ?checked=${'specific-urls'===o}
            @change=${h}
          />
          <label for="specific-urls">Specific URLs</label>
        </fieldset>

        ${'top-level-url'===o?_`
              <fieldset role="group">
                <input
                  type="url"
                  .value="${r}"
                  @input=${t=>{a(t.target.value)}}
                />
              </fieldset>
              <div style="display: flex;">
                <button
                  class="secondary outline"
                  style="margin-left: auto;"
                  @click=${()=>{a(e)}}
                >
                  Reset URL
                </button>
              </div>
            `:_`
              ${l.map((t,e)=>_`
                  <fieldset role="group">
                    <input
                      type="url"
                      @input=${t=>((t,e)=>{const s=[...l];s[t]=e.target.value,c(s)})(e,t)}
                    />
                    <button
                      type="button"
                      class="secondary outline"
                      @click=${()=>(t=>{const e=l.filter((e,s)=>s!==t);c(e)})(e)}
                    >
                      Delete
                    </button>
                  </fieldset>
                `)}
              <button @click=${()=>{c([...l,''])}}>Add URL</button>
            `}

        <details name="override-names" style="margin-top: 1em;">
          <summary>Name Configs</summary>
          <p>
            Some people go by multiple names that aren't easily guessable to be
            the same identity. Specify alternate names for identities to improve
            matching.
          </p>
          <name-config-form
            .onChange=${t=>{u(t)}}
            .existingNameConfigs=${d}
          ></name-config-form>
        </details>

        <footer>
          <button @click=${i.onClose} class="secondary">Cancel</button>
          <button
            @click=${()=>{(()=>{let e={};e='top-level-url'==o?{scrapeScope:o,data:{url:r}}:{scrapeScope:o,data:{sourceUrls:l}},e.identities=d,t(e)})(),i.onClose()}}
            class="primary"
            ?disabled=${!m}
          >
            Start Scrape
          </button>
        </footer>
      </article>
    </dialog>
  `},{useShadowDOM:!1})),customElements.define('civ-jurisdiction-page',Gt(function({jurisdiction_ocdid:t}){const[e,s]=dt(null),[i,o]=dt([]),[n,r]=dt(null),[a,l]=dt(!1),[c,d]=dt(null),[u,h]=dt(!1),[p,m]=dt(null),f=Kt(!1);at(()=>{t&&$()},[]);const $=async()=>{const[e,i,n]=await Promise.all([A(t),v(t),y(t)]);s(i),o(n),r(e)},g=(b=()=>{if(c)return;const e=`/api/sse/pipelines/status?jurisdiction_ocdid=${encodeURIComponent(t)}`;try{const t=new EventSource(e);d(t),m(null),t.onopen=()=>{h(!0),r(t=>({...t,status:'CONNECTED',message:'Waiting for updates...'}))},t.onmessage=e=>{try{const s=JSON.parse(e.data);r(s.data),'DONE'===s.data.status&&(t.close(),d(null),h(!1))}catch(t){m('Error processing update.')}},t.onerror=t=>{h(!1),m('Connection lost or failed.')}}catch(t){m('Failed to initialize connection.')}},ct(()=>b,[c,d]));var b;at(()=>()=>{c&&c.close()},[c]);const v=async t=>{const e=encodeURIComponent(t),s=await fetch(`/api/api_proxy/jurisdictions?jurisdiction_ocdid=${e}&with_geom=true`),i=await s.json();return{data:i.data,geo_center:i.geo_center}},y=async t=>{const e=encodeURIComponent(t),s=await fetch(`/api/api_proxy/people?jurisdiction_ocdid=${e}`);return(await s.json()).data},A=async t=>{const e=await fetch(`/api/pipelines/status?jurisdiction_ocdid=${encodeURIComponent(t)}`);if(!e.ok)return null;return(await e.json()).data},w=!n&&!a,S=e?.data?.updated_at?'Scraped':'Unscraped';return _`
    <div style="display: flex; flex-direction: column; gap: 2rem;">
      <div class="grid">
        <div>
          <civ-map
            canmove="false"
            .latlng=${e&&e.geo_center?{lat:e.geo_center.lat,lng:e.geo_center.lng}:null}
          ></civ-map>
        </div>

        <div>
          ${e?_`
                <header>
                  <div
                    style="display: flex; justify-content: space-between; align-items: center;"
                  >
                    <h2 style="margin-bottom: 0">${e.data.name}</h2>
                    <span style="font-size: 1.75rem"
                      >Status: ${S}</span
                    >
                  </div>
                </header>
                <hr />

                <p>
                  <strong>Jurisdiction OCDID:</strong> ${e.data.id} <br />
                  <strong>Website:</strong> ${e.data.url} <br />
                  <strong>Geoid:</strong> ${e.data.geoid} <br />
                  <strong>Population:</strong> ${e.data.population.toLocaleString()}
                  <br />
                </p>

                <h3>Scrape History</h3>
                <hr />
                <civ-scrape-history-list
                  .scrapeJobs=${[]}
                ></civ-scrape-history-list>

                <civ-scrape-modal
                  .onStartScrape=${async t=>{l(!0);const s={jurisdiction_ocdid:e.data.id,config:{url:t.data.url||e.data.url,name:e.data.name,source_urls:t.data.sourceUrls,identities:t.data.identities}};await fetch('/api/pipelines',{headers:{'Content-Type':'application/json'},method:'POST',body:JSON.stringify(s)}),g()}}
                  .url=${e.data.url}
                  .modalProps=${f.modalProps}
                ></civ-scrape-modal>

                <button
                  @click=${t=>{f.openModal()}}
                  ?disabled=${!w}
                  class="primary"
                >
                  Scrape Data for Jurisdiction
                </button>
              `:_` <p>Loading jurisdiction data...</p> `}
        </div>
      </div>

      ${u?_`
            <div class="status-banner success">
              <strong>Pipeline Status:</strong> ${n?.status} <br />
              <small>${n.message||''}</small>
            </div>
          `:null}

      <h2>Elected Representatives</h2>
      <civ-people-list .local=${i}></civ-people-list>
    </div>
  `},{useShadowDOM:!1,observedAttributes:['jurisdiction_ocdid']})),t();
