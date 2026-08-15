import fs from 'node:fs';
import path from 'node:path';

const CACHING_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad';
const CACHING_OPTIMIZED = '658327ea-f89d-4fab-a63d-7e88639e58f6';
const templatePath = path.resolve(process.cwd(), 'infra/cloudfront-spa.json');

const template = JSON.parse(fs.readFileSync(templatePath, 'utf8'));
const resources = template.Resources ?? {};
const errors = [];

function fail(message) {
  errors.push(message);
}

function resource(name, type) {
  const item = resources[name];
  if (!item) {
    fail(`Missing resource ${name}`);
    return null;
  }
  if (item.Type !== type) {
    fail(`${name} must be ${type} (got ${item.Type})`);
  }
  return item;
}

if (template.AWSTemplateFormatVersion !== '2010-09-09') {
  fail('Template must declare AWSTemplateFormatVersion 2010-09-09');
}

resource('HostingBucket', 'AWS::S3::Bucket');
resource('CitizenWebOriginAccessControl', 'AWS::CloudFront::OriginAccessControl');
resource('CitizenWebSecurityHeadersPolicy', 'AWS::CloudFront::ResponseHeadersPolicy');
resource('CitizenWebHtmlHeadersPolicy', 'AWS::CloudFront::ResponseHeadersPolicy');
resource('HostingBucketPolicy', 'AWS::S3::BucketPolicy');

const distribution = resource('CitizenWebDistribution', 'AWS::CloudFront::Distribution');
const config = distribution?.Properties?.DistributionConfig ?? {};
const origin = config.Origins?.[0];
const defaultBehavior = config.DefaultCacheBehavior ?? {};
const assetBehavior = (config.CacheBehaviors ?? []).find(
  (item) => item.PathPattern === '/assets/*',
);
const errorCodes = new Set((config.CustomErrorResponses ?? []).map((item) => item.ErrorCode));

if (!origin?.DomainName || !origin.OriginAccessControlId || !origin.S3OriginConfig) {
  fail('Distribution must declare an S3 origin with OriginAccessControlId');
}
if (defaultBehavior.ViewerProtocolPolicy !== 'redirect-to-https') {
  fail('Default cache behavior must redirect HTTP to HTTPS');
}
if (defaultBehavior.CachePolicyId !== CACHING_DISABLED) {
  fail('HTML/default behavior must use managed CachingDisabled');
}
if (!defaultBehavior.ResponseHeadersPolicyId) {
  fail('Default cache behavior must attach a response-headers policy');
}
if (!defaultBehavior.TargetOriginId) {
  fail('Default cache behavior must target the S3 origin');
}
if (!assetBehavior) {
  fail('Distribution must cache /assets/* separately');
} else if (assetBehavior.CachePolicyId !== CACHING_OPTIMIZED) {
  fail('/assets/* must use managed CachingOptimized');
}
if (!errorCodes.has(403) || !errorCodes.has(404)) {
  fail('SPA fallback requires custom error responses for 403 and 404');
}
for (const item of config.CustomErrorResponses ?? []) {
  if (item.ResponseCode !== 200 || item.ResponsePagePath !== '/index.html') {
    fail(`Error ${item.ErrorCode} must rewrite to 200 /index.html`);
  }
}

const publicImageOrigin = template.Parameters?.PublicImageOrigin ?? {};
if (
  publicImageOrigin.Type !== 'String' ||
  !String(publicImageOrigin.AllowedPattern ?? '').startsWith('^https://')
) {
  fail('PublicImageOrigin must be an HTTPS origin parameter for public photoUrl hosts');
}

function cspSource(resourceName) {
  const csp =
    resources[resourceName]?.Properties?.ResponseHeadersPolicyConfig?.SecurityHeadersConfig
      ?.ContentSecurityPolicy?.ContentSecurityPolicy;
  return typeof csp === 'string' ? csp : JSON.stringify(csp ?? '');
}

const htmlHeaders =
  resources.CitizenWebHtmlHeadersPolicy?.Properties?.ResponseHeadersPolicyConfig ?? {};
const security = htmlHeaders.SecurityHeadersConfig ?? {};
if (security.FrameOptions?.FrameOption !== 'DENY') {
  fail('HTML headers policy must set X-Frame-Options DENY');
}
if (!security.StrictTransportSecurity?.AccessControlMaxAgeSec) {
  fail('HTML headers policy must set HSTS');
}
if (!security.ContentTypeOptions) {
  fail('HTML headers policy must set X-Content-Type-Options');
}
const htmlCsp = cspSource('CitizenWebHtmlHeadersPolicy');
const assetCsp = cspSource('CitizenWebSecurityHeadersPolicy');
if (!htmlCsp.includes("frame-ancestors 'none'") || !htmlCsp.includes('connect-src')) {
  fail('HTML headers policy must include a CSP with frame-ancestors and connect-src');
}
for (const [name, cspText] of [
  ['HTML', htmlCsp],
  ['asset', assetCsp],
]) {
  if (!cspText.includes('img-src') || !cspText.includes('${PublicImageOrigin}')) {
    fail(`${name} CSP must allow PublicImageOrigin in img-src so approved public photos can load`);
  }
}
const cacheControl = (htmlHeaders.CustomHeadersConfig?.Items ?? []).find(
  (item) => item.Header === 'Cache-Control',
);
if (cacheControl?.Value !== 'no-store') {
  fail('HTML headers policy must send Cache-Control: no-store');
}

if (errors.length > 0) {
  for (const message of errors) {
    console.error(message);
  }
  process.exit(1);
}

console.log('Citizen-web CloudFront template checks passed.');
