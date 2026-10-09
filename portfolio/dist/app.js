(async () => {
  const fmt = n => Number(n).toLocaleString('en-US');
  const set = (id, text) => { document.getElementById(id).textContent = text; };
  try {
    const response = await fetch('evidence.json');
    if (!response.ok) throw new Error('Evidence report is unavailable. Follow the source repository for verification details.');
    const data = await response.json();
    const demo = data.demo;
    set('patients', fmt(demo.patients)); set('resources', fmt(demo.resources)); set('references', fmt(demo.references)); set('cases', `${demo.evaluation.case_count}/${demo.evaluation.case_count}`);
    const steps = {
      plan: ['SUPPORTED SEMANTICS', 'A fixed plan, with explicit filters.', 'The question compiles into a bounded query template. Patient association, latest recorded observation, numeric threshold, unit and active prescription are explicit.', {intent:'latest_lab_medication',lab_code:'4548-4',threshold:8,comparison:'gt',unit:'%',medication_code:'6809',limit:20}, 'Unsupported extra filters and clinical advice abstain rather than silently change meaning.'],
      graph: ['REFERENCE GRAPH', 'Follow recorded relationships.', 'The graph follows FHIR references to associate the observation and prescription with a patient. Clinical fields retain their source representation.', {patient_id:'Patient/p-000044',observation_id:data.example.source.resourceType+'/'+data.example.source.id,value:data.example.source.valueQuantity.value,unit:data.example.source.valueQuantity.unit,recorded_at:data.example.source.effectiveDateTime}, 'Illustrative subset of an actual evaluated result. Graph nodes and edges were reconciled against this dataset.'],
      source: ['EXACT SOURCE RECORD', 'Open the serialized FHIR evidence.', 'The running app retrieves this exact resource from HAPI. Evidence paths and values are checked against the source, including names, dates, units and reference strings.', data.example.source, 'Synthetic resource captured from the live release stack. HAPI may add server-managed metadata.'],
      provenance: ['ARTIFACT → CONFIRMED STAGE', 'Trace the record through ingestion.', 'Audit events identify the source file and position, canonical artifact hash, dataset, transformation version and confirmed target stage.', data.example.provenance, 'This hash covers canonical artifact JSON before server-managed metadata; it is not a claim that live-store drift was checked.'],
    };
    function activate(step) {
      const [label,title,description,value,note]=steps[step];
      set('trace-label',label);set('trace-title',title);set('trace-description',description);set('trace-json',JSON.stringify(value,null,2));set('trace-note',note);
      document.getElementById('trace-panel').setAttribute('aria-labelledby',`tab-${step}`);
      document.querySelectorAll('[data-step]').forEach(button=>{const active=button.dataset.step===step;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;});
    }
    const tabs=[...document.querySelectorAll('[data-step]')];
    tabs.forEach((button,index)=>{button.addEventListener('click',()=>activate(button.dataset.step));button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();activate(tabs[next].dataset.step);tabs[next].focus();}});});
    activate('plan');
    const checks=[['Dataset',`${fmt(demo.patients)} patients · seed ${demo.seed}`],['Data quality',`${demo.quality_rule_count} / ${demo.quality_rule_count} rules passed`],['Grounded retrieval',`${demo.evaluation.case_count} cases · ${demo.evaluation.page_count} pages`],['Exact live FHIR sources',`${demo.evaluation.source_count} checked · ${demo.evaluation.status}`],['FHIR schema','Pinned R4 4.0.1 + labeled JSON shape checks'],['Dataset SHA-256',demo.dataset_hash],['Verified at',data.verified_at]];
    checks.forEach(([name,value])=>{const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;if(name.includes('SHA'))dd.style.cssText='font-family:monospace;font-size:9px;overflow-wrap:anywhere;max-width:65%';row.append(dt,dd);document.getElementById('verification-list').append(row);});
    if(data.benchmark){const block=document.getElementById('benchmark');block.replaceChildren();const h=document.createElement('h3');h.textContent='1,000-patient live benchmark';block.append(h);for(const line of data.benchmark.presentation_lines){const p=document.createElement('p');p.textContent=line;block.append(p);}}
  } catch(error) {set('trace-description',error.message);document.getElementById('trace-description').className='error';}
})();
