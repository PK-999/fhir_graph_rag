// Record actual local app interactions; install browser tools with make setup.
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { mkdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(resolve(root,'apps/web/package.json'));
const { chromium, expect }=require('@playwright/test');
const origin=process.env.DEMO_WEB_URL || 'http://localhost:4010';
const output=resolve(root,'portfolio/dist/assets');
await mkdir(output,{recursive:true});
const browser=await chromium.launch();
const context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:resolve(root,'artifacts/release-demo/video'),size:{width:1440,height:1000}}});
const page=await context.newPage();
const pause=()=>page.waitForTimeout(1800);
try {
 await page.goto(origin); await expect(page.getByRole('heading',{name:'Knowledge Graph Dashboard'})).toBeVisible();await pause();
 await page.getByRole('link',{name:'Patients',exact:true}).click();await expect(page.getByRole('heading',{name:'Patient Registry'})).toBeVisible();await pause();
 await page.goto(`${origin}/patients/p-000044`);await page.getByRole('tab',{name:'FHIR',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'FHIR',exact:true})).toContainText('"resourceType": "Patient"');await pause();
 await page.getByRole('link',{name:'Graph Explorer',exact:true}).click();await expect(page.locator('.react-flow')).toBeVisible();await pause();
 await page.getByRole('link',{name:'Data Quality',exact:true}).click();await expect(page.getByText('success',{exact:true})).toBeVisible();await pause();
 await page.getByRole('link',{name:'AI Assistant',exact:true}).click();
 await page.getByRole('button',{name:'Find patients whose latest HbA1c is above 8% with active Metformin',exact:true}).click();
 await page.getByRole('button',{name:'Ask question',exact:true}).click();await expect(page.getByRole('table',{name:'Retrieved results'})).toBeVisible();await pause();
 const source=page.getByRole('article',{name:'Evidence Observation/p-000044-o-0096',exact:true});
 await source.getByRole('button',{name:'Inspect FHIR source',exact:true}).click();await expect(source.getByRole('region',{name:'FHIR source Observation/p-000044-o-0096'})).toContainText('"value": 9.1');await pause();
 await source.getByRole('button',{name:'Inspect provenance',exact:true}).click();await expect(source.getByRole('region',{name:'Provenance Observation/p-000044-o-0096'})).toContainText('"status": "available"');await pause();
 await page.locator('main').evaluate(element=>{element.scrollTop=0;});await page.screenshot({path:resolve(output,'question-explorer.png'),fullPage:true});
 await page.getByRole('button',{name:'Show lab history for Patient/p-000001',exact:true}).click();await page.getByRole('button',{name:'Ask question',exact:true}).click();await expect(page.getByRole('table',{name:'Retrieved results'})).toBeVisible();await pause();
 await page.getByRole('textbox',{name:'Question'}).fill('What treatment should these patients take?');await page.getByRole('button',{name:'Ask question',exact:true}).click();await expect(page.getByText('Unsupported question',{exact:true})).toBeVisible();await pause();
 const video=page.video();await context.close();const original=await video.path();
 const encoded=spawnSync('ffmpeg',['-y','-i',original,'-c:v','libx264','-preset','fast','-crf','27','-pix_fmt','yuv420p','-movflags','+faststart','-an',resolve(output,'walkthrough.mp4')],{encoding:'utf8'});
 if(encoded.status!==0) throw new Error('ffmpeg could not encode the recorded walkthrough. Original WebM is preserved.');
 console.log('Recorded and verified the local walkthrough at portfolio/dist/assets/walkthrough.mp4');
} finally {await context.close();await browser.close();}
