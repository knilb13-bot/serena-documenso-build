/** Executor público derivado do pipeline auditado. Importar não executa. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const LOCK='92767f6b48c0710364669c0270015a3d3f4e4b8ebbc00ac931d97041fe4b1fce';
const BASE='documenso/documenso@sha256:04ac1003006e1086404e5b3aa9d748e84d8c0fd4cc5ee28938d6face9eb799ec';
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const check=(condition,message)=>{if(!condition)throw new Error(message);};
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));

export function childEnvironment(heapMb) {
  check(Number.isInteger(heapMb) && heapMb>=256 && heapMb<=8192,'Heap não aprovado');
  return {
    PATH:'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',HOME:'/tmp',CI:'1',HUSKY:'0',
    NODE_OPTIONS:'--max-old-space-size='+heapMb,NODE_ENV:'production',DOCKER_OUTPUT:'1',
    NEXT_TELEMETRY_DISABLED:'1',DOCUMENSO_DISABLE_TELEMETRY:'1',TURBO_TELEMETRY_DISABLED:'1',
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:'1',NPM_CONFIG_USERCONFIG:'/work/user.npmrc',NPM_CONFIG_GLOBALCONFIG:'/work/global.npmrc',NPM_CONFIG_UPDATE_NOTIFIER:'false',
    NEXT_PUBLIC_WEBAPP_URL:'https://assinaturas-teste.serenanobre.cloud',NEXTAUTH_SECRET:'PUBLIC-SYNTHETIC-BUILD-ONLY-NOT-A-CREDENTIAL',
    NEXT_PRIVATE_ENCRYPTION_KEY:'CAFEBABE',NEXT_PRIVATE_ENCRYPTION_SECONDARY_KEY:'DEADBEEF',
    NEXT_PRIVATE_DATABASE_URL:'postgresql://fixture:fixture@127.0.0.1:1/fixture',
    NEXT_PRIVATE_DIRECT_DATABASE_URL:'postgresql://fixture:fixture@127.0.0.1:1/fixture',
  };
}
function run(args,cwd,env) {
  const result=spawnSync(args[0],args.slice(1),{cwd,env,encoding:'utf8',timeout:1800000,maxBuffer:32*1024*1024});
  // Captura somente logs de compilação sintética, nunca ambiente/configuração real.
  fs.appendFileSync('/out/builder.log',(result.stdout||'')+(result.stderr||''));
  check(result.status===0 && !result.error,'Comando falhou; parar sem repetir ou ampliar limites');
  return (result.stdout||'').trim();
}
export function safeSourceRelative(relative) {
  return typeof relative==='string'&&relative.length>0&&!/[\\:\x00-\x1f]/.test(relative)&&!path.posix.isAbsolute(relative)&&!path.win32.isAbsolute(relative)&&relative.split('/').every(part=>part!==''&&part!=='.'&&part!=='..');
}
function validateSource(root,index,expectedLock=LOCK) {
  check(hash(fs.readFileSync(path.join(root,'package-lock.json')))===expectedLock,'Lock alterado');
  for(const [relative,expected] of Object.entries(index.files)) {
    check(safeSourceRelative(relative),'Caminho não aprovado');
    check(hash(fs.readFileSync(path.join(root,relative)))===expected,'Fonte mudou');
  }
}
export function verifyPrunedLock(original,derived) {
  check(original.version==='2.21.1'&&derived.version==='2.21.1'&&derived.lockfileVersion===3,'Versão derivada inesperada');
  let count=0;
  for(const [key,value] of Object.entries(derived.packages||{})) {
    const before=original.packages?.[key];check(before,'Entrada nova no lock derivado');
    if(value.link) {check(before.link===true&&value.resolved===before.resolved,'Link de workspace mudou');continue;}
    if(key.includes('node_modules/')) {
      check(value.version===before.version&&value.resolved===before.resolved&&value.integrity===before.integrity,'Versão/URL/SRI mudou no prune');
      check(typeof value.resolved==='string'&&/^https:\/\/registry\.npmjs\.org\//.test(value.resolved)&&typeof value.integrity==='string'&&/sha(?:512|384|256)-/.test(value.integrity),'Lacuna externa no lock derivado');count++;
    } else {
      check(value.version===before.version,'Versão de workspace mudou');
      for(const field of ['dependencies','devDependencies','optionalDependencies']) {
        for(const [name,version] of Object.entries(value[field]||{}))check(before[field]?.[name]===version,'Dependência de workspace acrescentada/alterada');
      }
    }
  }
  check(!Object.hasOwn(derived.packages,'packages/app-tests/node_modules/@playwright/test'),'Lacuna app-tests não excluída');
  return {external_entries_verified:count,hole_excluded:true};
}
function indexTree(root) {
  const result={};
  function visit(folder) {
    for(const item of fs.readdirSync(folder,{withFileTypes:true})) {
      const target=path.join(folder,item.name);check(!item.isSymbolicLink(),'Link inesperado na fonte derivada');
      if(item.isDirectory())visit(target);
      else if(item.isFile())result[path.relative(root,target).split(path.sep).join('/')]=hash(fs.readFileSync(target));
    }
  }
  visit(root);return result;
}
export function copyRootBuildFiles(source,root) {
  function copy(relative) {
    const from=path.join(source,relative),to=path.join(root,relative),stat=fs.lstatSync(from);
    check(!stat.isSymbolicLink(),'Link inesperado nos arquivos raiz do build');
    if(stat.isDirectory()) {
      if(fs.existsSync(to))check(fs.lstatSync(to).isDirectory()&&!fs.lstatSync(to).isSymbolicLink(),'Destino raiz inesperado');
      else fs.mkdirSync(to,{recursive:true});
      for(const name of fs.readdirSync(from))copy(path.join(relative,name));
    } else {
      check(stat.isFile(),'Arquivo raiz inesperado');
      if(fs.existsSync(to))check(fs.lstatSync(to).isFile()&&!fs.lstatSync(to).isSymbolicLink()&&hash(fs.readFileSync(to))===hash(fs.readFileSync(from)),'Arquivo raiz divergente no prune');
      else {fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(from,to,fs.constants.COPYFILE_EXCL);}
    }
  }
  for(const relative of ['.gitignore','lingui.config.ts','turbo.json','patches'])copy(relative);
}
function packageBin(root,name,binName) {
  const folder=path.join(root,'node_modules',name),pkg=json(path.join(folder,'package.json'));
  const relative=typeof pkg.bin==='string'?pkg.bin:pkg.bin?.[binName];
  check(typeof relative==='string','Executável local ausente');
  const target=path.resolve(folder,relative);
  check(target.startsWith(folder+path.sep)&&fs.existsSync(target),'Executável fora do pacote');
  return [process.execPath,target];
}

const NATIVE_PUBLIC_PINS = [
  {package:'@documenso/skia-canvas',version:'3.0.8-documenso.3',file:'lib/skia.node',bytes:31538536,sha256:'4492d812e6d50c82e5978922b4a083afde56f97830338881e73eed388973e600',copy:true},
  {package:'@prisma/engines',version:'6.19.3',file:'schema-engine-linux-musl-openssl-3.0.x',bytes:19644784,sha256:'955e3bff1be23248a0922a219f7c4e200acc8fdd1fc72479557c0a9d782bd64a',env:'PRISMA_SCHEMA_ENGINE_BINARY'},
  {package:'@prisma/engines',version:'6.19.3',file:'libquery_engine-linux-musl-openssl-3.0.x.so.node',bytes:17556136,sha256:'28abc36457335e1a45fe2fe79a4c781b55347e696d6f4410c83bf232d92a726c',env:'PRISMA_QUERY_ENGINE_LIBRARY'},
];
// Somente binarios publicos da MESMA imagem base fixada; sem hook/download.
export function prepareNativePrerequisites(root,env,baseRoot='/app/node_modules',pins=NATIVE_PUBLIC_PINS) {
  const proof=[];
  for(const item of pins) {
    let didCopy=false;
    for(const modules of [baseRoot,path.join(root,'node_modules')]) {
      const pkg=json(path.join(modules,item.package,'package.json'));
      check(pkg.name===item.package&&pkg.version===item.version,'Versao do componente nativo divergiu');
    }
    const source=path.join(baseRoot,item.package,item.file),stat=fs.lstatSync(source);
    check(stat.isFile()&&!stat.isSymbolicLink()&&stat.size===item.bytes&&hash(fs.readFileSync(source))===item.sha256,'Binario publico nativo divergiu');
    if(item.copy) {
      const target=path.join(root,'node_modules',item.package,item.file);
      const parent=fs.lstatSync(path.dirname(target));
      check(parent.isDirectory()&&!parent.isSymbolicLink(),'Diretorio nativo inesperado');
      if(fs.existsSync(target)) {
        const before=fs.lstatSync(target);
        check(before.isFile()&&!before.isSymbolicLink()&&before.size===item.bytes&&hash(fs.readFileSync(target))===item.sha256,'Binario nativo existente divergiu; nao sobrescrever');
      } else { fs.copyFileSync(source,target,fs.constants.COPYFILE_EXCL); didCopy=true; }
      check(hash(fs.readFileSync(target))===item.sha256,'Copia do binario nativo divergiu');
    }
    if(item.env) env[item.env]=source;
    proof.push({package:item.package,version:item.version,file:item.file,bytes:item.bytes,sha256:item.sha256,copied:didCopy});
  }
  env.PRISMA_GENERATE_SKIP_AUTOINSTALL='1';
  env.CHECKPOINT_DISABLE='1';
  return proof;
}


// npm 11.19.1 cache.add aceita varios specs via Promise.all; lotes limitam RAM/FD.
export function dependencyCacheBatches(entries) {
  const batches=[];let batch=[],bytes=0;
  for(const entry of entries) {
    check(Number.isSafeInteger(entry.bytes)&&entry.bytes>0&&entry.bytes<=256*1024**2,'Tamanho de cache invalido');
    if(batch.length&&(batch.length>=8||bytes+entry.bytes>16*1024**2)) {
      batches.push(batch);batch=[];bytes=0;
    }
    batch.push(entry);bytes+=entry.bytes;
  }
  if(batch.length)batches.push(batch);
  return batches;
}

export function main(stage) {
  check(['prune','install','build'].includes(stage),'Etapa inválida');
  check(process.platform==='linux'&&process.arch==='x64'&&process.version==='v24.22.1','Runtime da imagem divergiu');
  const memory=Number(fs.readFileSync('/sys/fs/cgroup/memory.max','utf8').trim());
  const swap=fs.readFileSync('/sys/fs/cgroup/memory.swap.max','utf8').trim();
  const pids=Number(fs.readFileSync('/sys/fs/cgroup/pids.max','utf8').trim());
  const [quota,period]=fs.readFileSync('/sys/fs/cgroup/cpu.max','utf8').trim().split(/\s+/).map(Number);
  check(memory===10737418240&&swap==='0'&&pids===512&&quota/period===2,'Limites do CI divergiram');
  const env=childEnvironment(8192), root='/work/source';
  check(run(['npm','--version'],'/tmp',env)==='11.19.1','npm divergiu');
  for(const file of ['/work/user.npmrc','/work/global.npmrc']) {
    if(!fs.existsSync(file))fs.writeFileSync(file,'registry=https://registry.npmjs.org/\naudit=false\nfund=false\nignore-scripts=true\n');
  }
  const sourceIndex=json('/work/source-index.json');
  if(stage==='prune') {
    check(!fs.existsSync(root)&&!fs.existsSync('/work/source-prune')&&!fs.existsSync('/work/turbo-bootstrap')&&!fs.existsSync('/work/pruned'),'Prune anterior; não repetir');
    validateSource('/src',sourceIndex);
    const bootstrap=json('/work/bootstrap-index.json');
    check(bootstrap.entries.length===2&&bootstrap.entries.map(x=>x.name).sort().join(',')==='@turbo/linux-64,turbo','Bootstrap fora do escopo');
    for(const entry of bootstrap.entries) {
      check(entry.version==='2.10.5'&&hash(fs.readFileSync('/cache/'+entry.file))===entry.sha256,'Bootstrap alterado');
    }
    fs.mkdirSync('/work/turbo-bootstrap');
    fs.writeFileSync('/work/turbo-bootstrap/package.json','{"private":true,"name":"public-turbo-bootstrap","version":"0.0.0"}');
    run(['npm','install','--prefix=/work/turbo-bootstrap','--offline','--ignore-scripts','--omit=optional','--no-save','--package-lock=false','--no-audit','--no-fund',...bootstrap.entries.map(x=>'/cache/'+x.file)],'/work/turbo-bootstrap',env);
    fs.cpSync('/src','/work/source-prune',{recursive:true,errorOnExist:true,force:false});
    const binary='/work/turbo-bootstrap/node_modules/@turbo/linux-64/bin/turbo';
    check(run([binary,'--version'],'/work/source-prune',env)==='2.10.5','Turbo divergiu');
    run([binary,'prune','--scope=@documenso/remix','--docker','--out-dir=/work/pruned'],'/work/source-prune',env);
    const derived=fs.readFileSync('/work/pruned/package-lock.json');
    check(hash(derived)==='9c2d29755f01aa0d002145521c66d55656309c49d5c2bb29daee3363aabdf775','Lock derivado mudou');
    const proof=verifyPrunedLock(json('/src/package-lock.json'),JSON.parse(derived));
    fs.cpSync('/work/pruned/full',root,{recursive:true,errorOnExist:true,force:false});
    fs.cpSync('/work/pruned/json',root,{recursive:true,force:true});
    copyRootBuildFiles('/src',root);
    fs.writeFileSync(root+'/package-lock.json',derived);
    fs.writeFileSync('/out/pruned-package-lock.json',derived);
    fs.writeFileSync('/out/prune-proof.json',JSON.stringify({...proof,files:indexTree(root),source_index_sha256:hash(fs.readFileSync('/work/source-index.json')),derived_lock_sha256:hash(derived),network:'none'}));
    return;
  }
  const prune=json('/out/prune-proof.json');
  check(prune.source_index_sha256===hash(fs.readFileSync('/work/source-index.json')),'Fonte de outro prune');
  validateSource(root,prune,prune.derived_lock_sha256);
  if(stage==='install') {
    check(!fs.existsSync(root+'/node_modules'),'Install anterior; não repetir');
    const entries=json('/work/dependency-index.json').entries;
    for(const entry of entries) {
      check(/^[0-9a-f]{64}\.tgz$/.test(entry.file),'Cache inválido');
      const bytes=fs.readFileSync('/cache/'+entry.file);
      check(hash(bytes)===entry.sha256,'Cache mudou');
      const tokens=entry.integrity.split(/\s+/),algorithm=['sha512','sha384','sha256'].find(a=>tokens.some(t=>t.startsWith(a+'-')));
      check(algorithm&&tokens.includes(algorithm+'-'+crypto.createHash(algorithm).update(bytes).digest('base64')),'SRI inválido');
    }
    for(const [i,batch] of dependencyCacheBatches(entries).entries()) {
      console.log('cache batch '+(i+1));
      run(['npm','cache','add',...batch.map(x=>'/cache/'+x.file),'--offline','--ignore-scripts','--cache=/work/npm-cache','--no-audit','--no-fund'],root,env);
    }
    run(['npm','ci','--offline','--ignore-scripts','--cache=/work/npm-cache','--registry=https://registry.npmjs.org','--no-audit','--no-fund','--update-notifier=false','--include=dev'],root,env);
    validateSource(root,prune,prune.derived_lock_sha256);
    fs.writeFileSync('/out/install-proof.json',JSON.stringify({network:'none',lifecycle_scripts_executed:false,source_index_sha256:prune.source_index_sha256}));
    return;
  }
  const installed=json('/out/install-proof.json');
  check(installed.network==='none'&&installed.lifecycle_scripts_executed===false&&installed.source_index_sha256===prune.source_index_sha256,'Install sem prova');
  const nativePrerequisites=prepareNativePrerequisites(root,env);
  run([...packageBin(root,'patch-package','patch-package'),'--error-on-fail'],root,env);
  run([process.execPath,'--input-type=commonjs','-e',"const skia=require('./node_modules/@documenso/skia-canvas'); const c=new skia.Canvas(1,1); if(c.width!==1)throw Error('skia'); require('./node_modules/esbuild').transformSync('const n=1;', {loader:'js'}); require('./node_modules/sharp'); console.log('native-loaders-ok');"],root,env);
  run([...packageBin(root,'prisma','prisma'),'generate','--schema','packages/prisma/schema.prisma'],root,env);
  run([...packageBin(root,'@lingui/cli','lingui'),'compile'],root,env);
  const app=path.join(root,'apps/remix');
  run([...packageBin(root,'@react-router/dev','react-router'),'typegen'],app,env);
  run([...packageBin(root,'typescript','tsc')],app,env);
  run([...packageBin(root,'@react-router/dev','react-router'),'build'],app,env);
  run([...packageBin(root,'rollup','rollup'),'-c','rollup.config.mjs'],app,env);
  fs.copyFileSync(path.join(app,'server/main.js'),path.join(app,'build/server/main.js'));
  fs.cpSync(path.join(root,'packages/lib/translations'),path.join(app,'build/server/hono/packages/lib/translations'),{recursive:true});
  check(!fs.existsSync('/out/build')&&!fs.existsSync('/out/public'),'Saída existente; não sobrescrever');
  fs.cpSync(path.join(app,'build'),'/out/build',{recursive:true});
  fs.cpSync(path.join(app,'public'),'/out/public',{recursive:true});
  fs.writeFileSync('/out/build-proof.json',JSON.stringify({network:'none',database_connected:false,lock_sha256:LOCK,source_index_sha256:prune.source_index_sha256,native_prerequisites:nativePrerequisites,build_executed:true,signature_qa:false}));
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) main(process.argv[2]);
