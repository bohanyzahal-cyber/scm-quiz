// הדפסת בנק בצורה קריאה: node review.js <bank.js> [from] [to]
const fs=require('fs');
var BANK=[];eval(fs.readFileSync(process.argv[2],'utf8'));
const from=+(process.argv[3]||0), to=+(process.argv[4]||BANK.length);
const L='אבגד';
BANK.slice(from,to).forEach((q,j)=>{
  const i=from+j, lens=q.o.map(o=>o.length), mx=Math.max(...lens), mn=Math.min(...lens);
  const tag=lens[q.c]===mx?' [נכונה=ארוכה]':(lens[q.c]===mn?' [נכונה=קצרה]':'');
  console.log(`#${i}${tag}${q.k?' ['+q.k+']':''}  ${q.s}`);
  console.log('Q: '+q.q);
  q.o.forEach((o,k)=>console.log(`  ${k===q.c?'✓':' '}${L[k]} (${o.length}) ${o}`));
  console.log('E: '+q.e);
  console.log('');
});
