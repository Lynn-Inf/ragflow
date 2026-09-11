//
//  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
//
//  Licensed under the Apache License, Version 2.0 (the "License");
//  you may not use this file except in compliance with the License.
//  You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
//

package main

import (
	"os"
	"testing"
)

func parseArgsForTest(t *testing.T, argv ...string) (*serverArgs, error) {
	t.Helper()
	orig := os.Args
	os.Args = append([]string{"ragflow_server"}, argv...)
	defer func() { os.Args = orig }()
	return parseArgs()
}

func TestParseArgsMigrateIsStandalone(t *testing.T) {
	args, err := parseArgsForTest(t, "--migrate")
	if err != nil {
		t.Fatalf("parseArgs(--migrate) error = %v", err)
	}
	if !args.migrateDB {
		t.Fatal("migrateDB = false, want true")
	}
	if args.mode != nil {
		t.Fatalf("mode = %q, want nil: --migrate must not select a server mode", *args.mode)
	}
}

func TestParseArgsMigrateRejectsMode(t *testing.T) {
	for _, mode := range []string{"--api", "--admin", "--ingestor", "--syncer"} {
		if _, err := parseArgsForTest(t, mode, "--migrate"); err == nil {
			t.Errorf("parseArgs(%s --migrate) error = nil, want error", mode)
		}
		if _, err := parseArgsForTest(t, "--migrate", mode); err == nil {
			t.Errorf("parseArgs(--migrate %s) error = nil, want error", mode)
		}
	}
}

func TestParseArgsModeResetsMigrate(t *testing.T) {
	args, err := parseArgsForTest(t, "--api")
	if err != nil {
		t.Fatalf("parseArgs(--api) error = %v", err)
	}
	if args.mode == nil || *args.mode != "api" {
		t.Fatalf("mode = %v, want api", args.mode)
	}
	if args.migrateDB {
		t.Fatal("migrateDB = true, want false")
	}
}
