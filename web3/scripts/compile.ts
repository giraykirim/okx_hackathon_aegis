import fs from "node:fs";
import path from "node:path";
import solc from "solc";

const contractPath = path.resolve(__dirname, "../contracts/RiskDecisionRegistry.sol");
const source = fs.readFileSync(contractPath, "utf8");

const input = {
  language: "Solidity",
  sources: {
    "RiskDecisionRegistry.sol": {
      content: source,
    },
  },
  settings: {
    evmVersion: "paris",
    optimizer: {
      enabled: true,
      runs: 200,
    },
    outputSelection: {
      "*": {
        "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object"],
      },
    },
  },
};

const output = JSON.parse(solc.compile(JSON.stringify(input)));

if (output.errors) {
  const fatal = output.errors.filter((e: { severity: string }) => e.severity === "error");
  for (const err of output.errors) {
    console.error(err.formattedMessage);
  }
  if (fatal.length > 0) {
    process.exit(1);
  }
}

const compiled = output.contracts["RiskDecisionRegistry.sol"]["RiskDecisionRegistry"];
const artifactDir = path.resolve(__dirname, "../artifacts");
fs.mkdirSync(artifactDir, { recursive: true });

const artifact = {
  contractName: "RiskDecisionRegistry",
  compilerVersion: solc.version(),
  abi: compiled.abi,
  bytecode: `0x${compiled.evm.bytecode.object}`,
  deployedBytecode: `0x${compiled.evm.deployedBytecode.object}`,
};

const outPath = path.join(artifactDir, "RiskDecisionRegistry.json");
fs.writeFileSync(outPath, JSON.stringify(artifact, null, 2) + "\n", "utf8");
console.log(
  `Compiled RiskDecisionRegistry with solc ${solc.version()} -> ${outPath} (${
    compiled.evm.bytecode.object.length / 2
  } bytes)`
);
