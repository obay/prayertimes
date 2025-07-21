$Year = (Get-Date).year
$Month = (Get-Date).month
$Address = "Richmond, BC, Canada"
#$Address = "6 October, Cairo, Egypt"
$URL = "http://api.aladhan.com/v1/calendarByAddress?address=$Address&method=15&month=$Month&year=$Year"
$Data = (Invoke-WebRequest $URL | ConvertFrom-Json).Data

$objs = [System.Collections.ArrayList]::new()

for ($d = 0; $d -lt $Data.Length; $d++) {

    # Adding Imsak
    # $obj = New-Object -TypeName psobject
    # $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    # $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    # $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value $Times[$d].Imsak
    # $EndDate = (([datetime]::parseexact($Times[$d].Imsak, 'HH:mm', $null)) + (New-TimeSpan -Minutes 15))
    # $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($EndDate.Hour.ToString() + ":" + $EndDate.Minute.ToString())
    # $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Imsak"
    # [void]$objs.Add($obj)
    
    # Adding Sunrise
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Sunrise).split(" ")[0]
    $EndDate = (([datetime]::parseexact(($Data[0].timings.sunrise).split(" ")[0], 'HH:mm', $null)) + (New-TimeSpan -Minutes 15))
    # $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($EndDate.Hour.ToString() + ":" + $EndDate.Minute.ToString())
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Sunrise).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Sunrise"
    [void]$objs.Add($obj)

    # Adding Fajr
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Fajr).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Fajr).split(" ")[0]
    # $EndDate = (([datetime]::parseexact($Data[$d].timings.Fajr, 'HH:mm', $null)) + (New-TimeSpan -Minutes 15))
    # $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($EndDate.Hour.ToString() + ":" + $EndDate.Minute.ToString())
    $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Fajr"
    [void]$objs.Add($obj)
        
    # Adding Dhuhr
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Dhuhr).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Dhuhr).split(" ")[0]
    if (([datetime]::parseexact($Data[$d].date.gregorian.date, 'dd-MM-yyyy', $null)).DayOfWeek -eq "Friday") {
        $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Friday Prayer"
    }
    else {
        $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Dhuhr"
    }
    [void]$objs.Add($obj)
        
    # Adding Asr
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Asr).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Asr).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Asr"
    [void]$objs.Add($obj)
        
    # Adding Maghrib
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Maghrib).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Maghrib).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Maghrib"
    [void]$objs.Add($obj)

    # Adding Isha
    $obj = New-Object -TypeName psobject
    $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value ($Data[$d].timings.Isha).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($Data[$d].timings.Isha).split(" ")[0]
    $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Isha"
    [void]$objs.Add($obj)

    # Adding Midnight
    # $obj = New-Object -TypeName psobject
    # $obj | Add-Member -MemberType NoteProperty -Name "Start Date" -Value $Data[$d].date.gregorian.date
    # $obj | Add-Member -MemberType NoteProperty -Name "End Date" -Value $Data[$d].date.gregorian.date
    # $obj | Add-Member -MemberType NoteProperty -Name "Start Time" -Value $Data[$d].timings.Midnight
    # $EndDate = (([datetime]::parseexact($Data[$d].timings.Midnight, 'HH:mm', $null)) + (New-TimeSpan -Minutes 15))
    # $obj | Add-Member -MemberType NoteProperty -Name "End Time" -Value ($EndDate.Hour.ToString() + ":" + $EndDate.Minute.ToString())
    # $obj | Add-Member -MemberType NoteProperty -Name "Subject" -Value "Midnight"
    # [void]$objs.Add($obj)
}

$TimeStamp = Get-Date -Format yyyyMMddHHmm
$objs | ConvertTo-Csv | Out-File ./PrayerTimes-$TimeStamp.csv


# gcalcli import --calendar "Prayer Times" ./PrayerTimes-$TimeStamp.csv
