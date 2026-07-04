import fs from 'fs';
import path from 'path';
import openapiTS from 'openapi-typescript';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function run() {
  const inputPath = path.resolve(__dirname, '../libs/api-contracts/openapi/specs.yml');
  const outputPath = path.resolve(__dirname, '../libs/api-contracts/gen/ts/api-client.ts');

  if (!fs.existsSync(inputPath)) {
    console.warn(`Warning: OpenAPI specs file not found at ${inputPath}. Creating a dummy specs file.`);
    fs.mkdirSync(path.dirname(inputPath), { recursive: true });
    fs.writeFileSync(inputPath, `openapi: 3.0.0
info:
  title: SaaS PM+FinOps API
  version: 0.1.0
paths:
  /healthz:
    get:
      responses:
        '200':
          description: OK
`);
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  console.log(`Generating types from ${inputPath}...`);
  try {
    const ast = await openapiTS(new URL(`file://${inputPath}`));
    fs.writeFileSync(outputPath, ast);
    console.log(`Successfully generated: ${outputPath}`);
  } catch (err) {
    console.error('Error generating OpenAPI types:', err);
    process.exit(1);
  }
}

run();
