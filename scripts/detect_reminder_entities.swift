#!/usr/bin/env swift
import Foundation
import NaturalLanguage

struct DetectionResult: Codable {
    let PersonalName: [String]
    let OrganizationName: [String]
}

func uniqueInSourceOrder(_ values: [String]) -> [String] {
    var seen = Set<String>()
    return values.filter { value in
        guard !value.isEmpty, !seen.contains(value) else { return false }
        seen.insert(value)
        return true
    }
}

guard
    let input = try? FileHandle.standardInput.readToEnd(),
    let texts = try? JSONDecoder().decode([String].self, from: input)
else {
    exit(2)
}

let results = texts.map { text -> DetectionResult in
    let tagger = NLTagger(tagSchemes: [.nameType])
    tagger.string = text
    var people: [String] = []
    var organizations: [String] = []
    let range = text.startIndex..<text.endIndex
    tagger.enumerateTags(
        in: range,
        unit: .word,
        scheme: .nameType,
        options: [.omitPunctuation, .omitWhitespace, .joinNames]
    ) { tag, tokenRange in
        guard let tag else { return true }
        let value = String(text[tokenRange])
        if tag == .personalName {
            people.append(value)
        } else if tag == .organizationName {
            organizations.append(value)
        }
        return true
    }
    return DetectionResult(
        PersonalName: uniqueInSourceOrder(people),
        OrganizationName: uniqueInSourceOrder(organizations)
    )
}

guard let output = try? JSONEncoder().encode(results) else {
    exit(3)
}
FileHandle.standardOutput.write(output)
