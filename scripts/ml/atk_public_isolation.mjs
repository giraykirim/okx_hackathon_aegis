// This research collector must never discover an existing OKX profile or OAuth state.
import os from 'node:os';
import { syncBuiltinESMExports } from 'node:module';
if (!process.env.AEGIS_ATK_HOME) throw new Error('Empty isolated ATK home required');
os.homedir = () => process.env.AEGIS_ATK_HOME;
syncBuiltinESMExports();
