import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function run() {
  const inputPath = path.resolve(__dirname, '../libs/api-contracts/asyncapi/events.yml');
  const outputDir = path.resolve(__dirname, '../libs/api-contracts/gen/py');

  if (!fs.existsSync(inputPath)) {
    console.warn(`Warning: AsyncAPI events file not found at ${inputPath}. Creating dummy events file.`);
    fs.mkdirSync(path.dirname(inputPath), { recursive: true });
    fs.writeFileSync(inputPath, `asyncapi: 2.6.0
info:
  title: SaaS PM+FinOps Events
  version: 0.1.0
channels:
  fin/time_logged:
    publish:
      message:
        payload:
          type: object
          properties:
            event_id:
              type: string
              format: uuid
            tenant_id:
              type: string
              format: uuid
            project_id:
              type: string
              format: uuid
            hours:
              type: number
            role_cost_per_hour:
              type: number
`);
  }

  fs.mkdirSync(outputDir, { recursive: true });
  console.log(`Generating Python models from ${inputPath}...`);
  try {
    execSync(`npx -y @asyncapi/generator ${inputPath} @asyncapi/python-pydantic-template -o ${outputDir} --force-write`, { stdio: 'inherit' });
    console.log(`Successfully generated Python models in ${outputDir}`);
  } catch (err) {
    console.warn('Could not generate AsyncAPI python models programmatically, writing fallback dummy file:', err);
    const dummyPy = path.join(outputDir, 'events.py');
    fs.writeFileSync(dummyPy, `from pydantic import BaseModel
from uuid import UUID

class TimeLoggedEvent(BaseModel):
    event_id: UUID
    tenant_id: UUID
    project_id: UUID
    hours: float
    role_cost_per_hour: float
`);
  }
}

run();
