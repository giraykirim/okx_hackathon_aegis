// Isolate ATK profiles, OAuth state and logs without changing the user's HOME.
import os from 'node:os';
import { syncBuiltinESMExports } from 'node:module';
if (!process.env.AEGIS_ATK_HOME) throw new Error('Isolated ATK directory required');
os.homedir = () => process.env.AEGIS_ATK_HOME;
syncBuiltinESMExports();
