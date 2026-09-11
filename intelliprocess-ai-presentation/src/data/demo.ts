export type WorkflowStage = {
  label: string;
  status: 'done' | 'active' | 'pending';
};

export const demoWorkflow: WorkflowStage[] = [
  { label: 'Upload', status: 'done' },
  { label: 'Extract', status: 'done' },
  { label: 'Match', status: 'active' },
  { label: 'Review', status: 'pending' },
  { label: 'Approve', status: 'pending' },
];

export const invoiceFields = [
  'Vendor',
  'Invoice Number',
  'Invoice Date',
  'Due Date',
  'Subtotal',
  'Tax',
  'Total',
  'PO Reference',
];

export const architectureLayers = [
  'React + TypeScript',
  'Amazon Cognito',
  'API Gateway',
  'AWS Lambda',
  'S3 + DynamoDB',
  'Amazon Bedrock',
  'Bedrock Data Automation',
  'Bedrock Knowledge Bases',
];

export const demoRecords = [
  { title: 'Supplier policy', excerpt: 'All vendor invoices require PO and GR validation before approval.', category: 'Policy' },
  { title: 'Procurement agreement', excerpt: 'Approved vendors are matched against purchase orders before payment release.', category: 'Contract' },
  { title: 'Finance procedure', excerpt: 'Escalated invoices are reviewed by the finance manager with reason codes.', category: 'Finance' },
];
