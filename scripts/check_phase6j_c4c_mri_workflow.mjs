#!/usr/bin/env node
// C4C synthetic browser checks; no patient material or ML inference.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = path => readFileSync(resolve(root, path), 'utf8');
const js = read('web/js/mri-workflow-display.js');
const { isReadOnlyMri, workflowMatchesStudy } = await import('data:text/javascript,' + encodeURIComponent(js));
const uid='1.2.840.1';
const study = { study_id:'a'.repeat(32), reconstruction_series_uid:uid,
  series:[{series_instance_uid:uid, modality:'MR'}], volume_ready:true };
const mr = {study_id:study.study_id, source_series_uid:uid, modality:'MR',
  model_id:'total_mr', presentation_only:true, state:'running', can_start:true, can_use:true};
assert.equal(isReadOnlyMri(mr), true);
assert.equal(workflowMatchesStudy(mr,study),true);
for(const bad of [ {...mr,study_id:'b'.repeat(32)}, {...mr,source_series_uid:'1.2.999'},
  {...mr,modality:'CT'}, {...mr,model_id:'total'}, {...mr,source_series_uid:null} ]){
  assert.equal(workflowMatchesStudy(bad,study),false);
}
assert.equal(workflowMatchesStudy(mr,{...study,reconstruction_series_uid:'1.2.998'}),false);
const ctStudy={...study,series:[{series_instance_uid:uid,modality:'CT'}]};
assert.equal(workflowMatchesStudy(mr,ctStudy),false);
assert.equal(workflowMatchesStudy({study_id:study.study_id,modality:'CT',model_id:'total'},ctStudy),true);
assert.equal(isReadOnlyMri({modality:'CT',model_id:'total'}),false);
class Element {
 constructor(){this.dataset={};this.textContent='';this.disabled=false;this.hidden=false;this.style={};this.attributes={};}
 addEventListener(){} setAttribute(k,v){this.attributes[k]=v;}
}
globalThis.HTMLElement=Element;
const {SegmentationWorkflowPanel}=await import('data:text/javascript,'+encodeURIComponent(read('web/js/segmentation-workflow-panel.js')));
const nodes=new Map(); const rootNode=new Element();
rootNode.querySelector=s=>{if(!nodes.has(s))nodes.set(s,new Element());return nodes.get(s);};
const panel=new SegmentationWorkflowPanel(rootNode);
for(const state of ['idle','failed','cancelled','output_ready','available']){
 panel.render({...mr,state,label_map_id:'map-'+ 'a'.repeat(32)});
 assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled,true,state);
 assert.equal(nodes.get('#segmentationWorkflowPrimary').textContent,'Start Segmentation',state);
}
panel.render({...mr,state:'running',can_cancel:true,progress:{percent:15,message:'Working'}});
assert.equal(nodes.get('#segmentationWorkflowCancel').disabled,false);
assert.equal(nodes.get('#segmentationWorkflowPrimary').hidden,true);
panel.render({study_id:study.study_id,modality:'CT',model_id:'total',state:'idle',can_start:true});
assert.equal(nodes.get('#segmentationWorkflowPrimary').disabled,false);
assert.equal(nodes.get('#segmentationWorkflowPrimary').textContent,'Start Segmentation');
const app=read('web/js/app.js');
assert.match(app,/workflowMatchesStudy\(workflow, state\.study\)/);
assert.match(app,/isReadOnlyMri\(segmentationWorkflowSnapshot\)/);
assert.match(app,/isReadOnlyMri\(workflow\)/);
assert.match(app,/segmentationWorkflowGeneration \+= 1;/);
assert.match(read('web/index.html'),/phase6j-c4c-r1/);
console.log('PHASE6J_C4C_MRI_PRESENTATION_AND_STUDY_ISOLATION=PASS');
console.log('PHASE6J_C4C_CT_AND_EXECUTION_GATES=PASS');
