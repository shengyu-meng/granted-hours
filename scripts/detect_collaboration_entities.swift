#!/usr/bin/env swift
import Foundation
import NaturalLanguage

struct DetectionResult: Codable {
    let PrivateEntityTerms: [String]
}

func uniqueInSourceOrder(_ values: [String]) -> [String] {
    var seen = Set<String>()
    return values.filter { value in
        let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty, !seen.contains(normalized) else { return false }
        seen.insert(normalized)
        return true
    }
}

guard
    let input = try? FileHandle.standardInput.readToEnd(),
    let texts = try? JSONDecoder().decode([String].self, from: input)
else { exit(2) }

let results = texts.map { text -> DetectionResult in
    let tagger = NLTagger(tagSchemes: [.nameType])
    tagger.string = text
    var terms: [String] = []
    tagger.enumerateTags(
        in: text.startIndex..<text.endIndex,
        unit: .word,
        scheme: .nameType,
        options: [.omitPunctuation, .omitWhitespace, .joinNames]
    ) { tag, tokenRange in
        if tag == .personalName || tag == .organizationName || tag == .placeName {
            terms.append(String(text[tokenRange]))
        }
        return true
    }
    return DetectionResult(PrivateEntityTerms: uniqueInSourceOrder(terms))
}

guard let output = try? JSONEncoder().encode(results) else { exit(3) }
FileHandle.standardOutput.write(output)
