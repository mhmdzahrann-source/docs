(function(){
  /* mobile menu */
  var btn=document.getElementById('menuBtn'),dr=document.getElementById('drawer');
  if(btn&&dr){
    btn.addEventListener('click',function(){var open=dr.hidden;dr.hidden=!open;btn.setAttribute('aria-expanded',String(open));btn.setAttribute('aria-label',open?'Close menu':'Open menu');});
    dr.addEventListener('click',function(e){if(e.target.closest('a')){dr.hidden=true;btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-label','Open menu');}});
  }
  /* search toggle */
  var sBtn=document.getElementById('searchBtn'),sBar=document.getElementById('searchBar');
  if(sBtn&&sBar){sBtn.addEventListener('click',function(){var open=sBar.hidden;sBar.hidden=!open;sBtn.setAttribute('aria-expanded',String(open));if(open){var i=sBar.querySelector('input');if(i)i.focus();}});}

  /* portfolio filters */
  document.querySelectorAll('[data-filters]').forEach(function(group){
    var root=group.closest('section'),fs=group.querySelectorAll('button'),cards=root.querySelectorAll('.pf-card');
    fs.forEach(function(b){b.addEventListener('click',function(){
      var f=b.dataset.f;
      fs.forEach(function(x){x.setAttribute('aria-pressed',String(x===b));});
      cards.forEach(function(c){var show=f==='all'||c.dataset.k===f;c.hidden=!show;if(show){c.style.animation='none';void c.offsetWidth;c.style.animation='';}});
    });});
  });

  /* count-up stats */
  var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nums=document.querySelectorAll('[data-count]');
  if(!reduce&&'IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting)return;io.unobserve(e.target);
      var el=e.target,to=+el.dataset.count,t0=null;
      function step(t){if(!t0)t0=t;var p=Math.min(1,(t-t0)/1800);el.textContent=Math.round(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(step);}
      requestAnimationFrame(step);});},{threshold:.4});
    nums.forEach(function(n){io.observe(n);});
  }

  /* product page: variants, gallery, quantity */
  document.querySelectorAll('[data-product-form]').forEach(function(form){
    var dataEl=form.querySelector('script[type="application/json"]');
    if(!dataEl)return;
    var variants=JSON.parse(dataEl.textContent);
    var idInput=form.querySelector('input[name="id"]');
    var addBtn=form.querySelector('[data-add-btn]');
    var priceEl=document.querySelector('[data-price]');
    var money=form.dataset.moneyFormat||'{{amount}}';
    function fmt(c){var a=(c/100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g,',');return money.replace(/\{\{\s*amount[a-z_]*\s*\}\}/,a);}
    function selected(){return Array.prototype.map.call(form.querySelectorAll('.opt'),function(fs){var c=fs.querySelector('input:checked');return c?c.value:null;});}
    function update(){
      var opts=selected();
      var v=variants.find(function(x){return x.options.every(function(o,i){return o===opts[i];});});
      if(!v){addBtn.disabled=true;addBtn.textContent=addBtn.dataset.unavailable;return;}
      idInput.value=v.id;
      addBtn.disabled=!v.available;
      addBtn.textContent=v.available?addBtn.dataset.add:addBtn.dataset.soldout;
      if(priceEl){priceEl.innerHTML=fmt(v.price)+(v.compare_at_price>v.price?' <s>'+fmt(v.compare_at_price)+'</s>':'');}
      if(v.featured_image){var m=document.querySelector('.gallery-main img');if(m){m.src=v.featured_image.src;m.removeAttribute('srcset');}}
      var url=new URL(window.location.href);url.searchParams.set('variant',v.id);history.replaceState(null,'',url);
    }
    form.querySelectorAll('.opt input').forEach(function(i){i.addEventListener('change',update);});
  });
  document.querySelectorAll('[data-thumb]').forEach(function(t){
    t.addEventListener('click',function(){
      var m=document.querySelector('.gallery-main img');if(!m)return;
      m.src=t.dataset.thumb;m.removeAttribute('srcset');
      document.querySelectorAll('[data-thumb]').forEach(function(x){x.setAttribute('aria-current',String(x===t));});
    });
  });
  document.querySelectorAll('.qty').forEach(function(q){
    var i=q.querySelector('input');
    q.querySelectorAll('button').forEach(function(b){b.addEventListener('click',function(){
      var v=(parseInt(i.value,10)||0)+(+b.dataset.step);var min=parseInt(i.min||'0',10);i.value=Math.max(min,v);
      i.dispatchEvent(new Event('change',{bubbles:true}));
    });});
  });
  /* cart: auto-submit on quantity change */
  var cartForm=document.getElementById('cartForm');
  if(cartForm){cartForm.addEventListener('change',function(e){if(e.target.matches('input[name="updates[]"]'))cartForm.submit();});}

  /* address country default */
  document.querySelectorAll('select[data-default]').forEach(function(s){if(s.dataset.default)s.value=s.dataset.default;});

  /* collection sort */
  var sort=document.getElementById('SortBy');
  if(sort){sort.addEventListener('change',function(){var u=new URL(window.location.href);u.searchParams.set('sort_by',sort.value);u.searchParams.delete('page');window.location.href=u.toString();});}
})();
